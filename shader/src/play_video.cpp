// See play_video.h.
#include "play_video.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>

namespace jf::play {

namespace {

#include "../spirv/copy_frag.h"
#include "../spirv/crt_frag.h"
#include "../spirv/screen_vert.h"

// The uniform block of the fragment shaders (std140: vec4 members only).
struct ScreenUniforms {
    float dst[4]; // picture rectangle in window pixels
    float src[4]; // frame width, height, 0, 0
};

bool ends_with(const std::string& s, const char* tail) {
    const size_t n = std::strlen(tail);
    if (s.size() < n) return false;
    for (size_t i = 0; i < n; ++i)
        if (std::tolower(static_cast<unsigned char>(s[s.size() - n + i])) != tail[i]) return false;
    return true;
}

} // namespace

PictureRect picture_rect(const std::string& scaling, double overscan, int ww, int wh, double cw, double ch) {
    PictureRect r;
    if (scaling == "stretch") {
        r.w = ww;
        r.h = wh;
        return r;
    }
    double dw = 0, dh = 0;
    if (scaling == "integer" || scaling == "overscan") {
        int k = static_cast<int>(std::floor(std::min(wh / ch, ww / cw)));
        if (scaling == "overscan") {
            // One step larger when the part cut off stays within the
            // overscan limit in both directions (a television hides
            // several percent at each edge).
            const int k1 = std::max(1, k + 1);
            const double h1 = k1 * ch, w1 = std::round(k1 * cw);
            if ((h1 - wh) / h1 <= overscan && (w1 - ww) / w1 <= overscan) k = k1;
        }
        if (k >= 1) {
            dh = k * ch;
            dw = std::round(k * cw);
        }
    }
    if (dw <= 0) {
        const double s = std::min(ww / cw, wh / ch);
        dw = cw * s;
        dh = ch * s;
    }
    r.x = std::floor((ww - dw) / 2);
    r.y = std::floor((wh - dh) / 2);
    r.w = dw;
    r.h = dh;
    return r;
}

bool Video::open(const std::string& title, int w, int h, bool fullscreen, bool want_vsync, const std::string& backend,
                 std::string* error) {
    SDL_WindowFlags flags = SDL_WINDOW_RESIZABLE | SDL_WINDOW_HIGH_PIXEL_DENSITY;
    if (fullscreen) flags |= SDL_WINDOW_FULLSCREEN;
    window_ = SDL_CreateWindow(title.c_str(), w, h, flags);
    if (!window_) {
        *error = SDL_GetError();
        return false;
    }
    if (backend == "gpu") {
        std::string why;
        if (open_gpu(want_vsync, &why)) return true;
        std::fprintf(stderr, "mamr_play: video: no GPU path (%s), the renderer draws\n", why.c_str());
    }
    return open_renderer(want_vsync, error);
}

bool Video::open_renderer(bool want_vsync, std::string* error) {
    renderer_ = SDL_CreateRenderer(window_, nullptr);
    if (!renderer_) {
        *error = SDL_GetError();
        return false;
    }
    vsync_ = want_vsync;
    if (!SDL_SetRenderVSync(renderer_, want_vsync ? 1 : 0)) {
        std::fprintf(stderr, "mamr_play: vsync %s: %s\n", want_vsync ? "on" : "off", SDL_GetError());
        int v = 0;
        SDL_GetRenderVSync(renderer_, &v);
        vsync_ = v != 0;
    }
    SDL_SetRenderDrawColor(renderer_, 0, 0, 0, 255);
    std::fprintf(stderr, "mamr_play: video: renderer %s\n", SDL_GetRendererName(renderer_));
    return true;
}

bool Video::open_gpu(bool want_vsync, std::string* why) {
    device_ = SDL_CreateGPUDevice(SDL_GPU_SHADERFORMAT_SPIRV, false, "vulkan");
    if (!device_) {
        *why = std::string("no Vulkan device: ") + SDL_GetError();
        return false;
    }
    if (!SDL_ClaimWindowForGPUDevice(device_, window_)) {
        *why = std::string("window: ") + SDL_GetError();
        SDL_DestroyGPUDevice(device_);
        device_ = nullptr;
        return false;
    }
    // Present mode: vsync is FIFO (always there); without vsync the
    // immediate mode, else mailbox, else FIFO after all.
    SDL_GPUPresentMode mode = SDL_GPU_PRESENTMODE_VSYNC;
    if (!want_vsync) {
        if (SDL_WindowSupportsGPUPresentMode(device_, window_, SDL_GPU_PRESENTMODE_IMMEDIATE))
            mode = SDL_GPU_PRESENTMODE_IMMEDIATE;
        else if (SDL_WindowSupportsGPUPresentMode(device_, window_, SDL_GPU_PRESENTMODE_MAILBOX))
            mode = SDL_GPU_PRESENTMODE_MAILBOX;
    }
    if (!SDL_SetGPUSwapchainParameters(device_, window_, SDL_GPU_SWAPCHAINCOMPOSITION_SDR, mode)) {
        *why = std::string("swapchain: ") + SDL_GetError();
        close_gpu();
        return false;
    }
    vsync_ = mode == SDL_GPU_PRESENTMODE_VSYNC;
    if (!want_vsync && vsync_) std::fprintf(stderr, "mamr_play: vsync off: the swapchain only has vsync\n");
    // One frame in flight: the next frame's commands wait for the last
    // one, so the picture is at most one frame behind the machine.
    SDL_SetGPUAllowedFramesInFlight(device_, 1);
    target_format_ = SDL_GetGPUSwapchainTextureFormat(device_, window_);

    auto shader = [&](const std::uint32_t* code, size_t bytes, SDL_GPUShaderStage stage, Uint32 samplers,
                      Uint32 uniforms) {
        SDL_GPUShaderCreateInfo si{};
        si.code_size = bytes;
        si.code = reinterpret_cast<const Uint8*>(code);
        si.entrypoint = "main";
        si.format = SDL_GPU_SHADERFORMAT_SPIRV;
        si.stage = stage;
        si.num_samplers = samplers;
        si.num_uniform_buffers = uniforms;
        return SDL_CreateGPUShader(device_, &si);
    };
    SDL_GPUShader* vs = shader(spirv_screen_vert, sizeof(spirv_screen_vert), SDL_GPU_SHADERSTAGE_VERTEX, 0, 0);
    SDL_GPUShader* fs_copy = shader(spirv_copy_frag, sizeof(spirv_copy_frag), SDL_GPU_SHADERSTAGE_FRAGMENT, 1, 1);
    SDL_GPUShader* fs_crt = shader(spirv_crt_frag, sizeof(spirv_crt_frag), SDL_GPU_SHADERSTAGE_FRAGMENT, 2, 1);
    auto pipeline = [&](SDL_GPUShader* fs) -> SDL_GPUGraphicsPipeline* {
        if (!vs || !fs) return nullptr;
        SDL_GPUColorTargetDescription ct{};
        ct.format = target_format_;
        SDL_GPUGraphicsPipelineCreateInfo pi{};
        pi.vertex_shader = vs;
        pi.fragment_shader = fs;
        pi.primitive_type = SDL_GPU_PRIMITIVETYPE_TRIANGLELIST;
        pi.rasterizer_state.fill_mode = SDL_GPU_FILLMODE_FILL;
        pi.rasterizer_state.cull_mode = SDL_GPU_CULLMODE_NONE;
        pi.target_info.color_target_descriptions = &ct;
        pi.target_info.num_color_targets = 1;
        return SDL_CreateGPUGraphicsPipeline(device_, &pi);
    };
    pipe_copy_ = pipeline(fs_copy);
    pipe_crt_ = pipeline(fs_crt);
    if (!pipe_copy_ || !pipe_crt_) *why = std::string("shaders: ") + SDL_GetError();
    if (vs) SDL_ReleaseGPUShader(device_, vs);
    if (fs_copy) SDL_ReleaseGPUShader(device_, fs_copy);
    if (fs_crt) SDL_ReleaseGPUShader(device_, fs_crt);
    if (!pipe_copy_ || !pipe_crt_) {
        close_gpu();
        return false;
    }
    SDL_GPUSamplerCreateInfo sa{};
    sa.min_filter = SDL_GPU_FILTER_NEAREST;
    sa.mag_filter = SDL_GPU_FILTER_NEAREST;
    sa.mipmap_mode = SDL_GPU_SAMPLERMIPMAPMODE_NEAREST;
    sa.address_mode_u = SDL_GPU_SAMPLERADDRESSMODE_CLAMP_TO_EDGE;
    sa.address_mode_v = SDL_GPU_SAMPLERADDRESSMODE_CLAMP_TO_EDGE;
    sa.address_mode_w = SDL_GPU_SAMPLERADDRESSMODE_CLAMP_TO_EDGE;
    sampler_ = SDL_CreateGPUSampler(device_, &sa);
    if (!sampler_) {
        *why = std::string("sampler: ") + SDL_GetError();
        close_gpu();
        return false;
    }
    SDL_PropertiesID props = SDL_GetGPUDeviceProperties(device_);
    const char* name = props ? SDL_GetStringProperty(props, SDL_PROP_GPU_DEVICE_NAME_STRING, "") : "";
    const char* drv = props ? SDL_GetStringProperty(props, SDL_PROP_GPU_DEVICE_DRIVER_NAME_STRING, "") : "";
    const char* ver = props ? SDL_GetStringProperty(props, SDL_PROP_GPU_DEVICE_DRIVER_VERSION_STRING, "") : "";
    std::fprintf(stderr, "mamr_play: video: gpu %s (%s, %s %s)\n", SDL_GetGPUDeviceDriver(device_), name, drv, ver);
    return true;
}

void Video::close_gpu() {
    if (!device_) return;
    SDL_WaitForGPUIdle(device_);
    if (upload_) SDL_ReleaseGPUTransferBuffer(device_, upload_);
    if (frame_tex_) SDL_ReleaseGPUTexture(device_, frame_tex_);
    if (sampler_) SDL_ReleaseGPUSampler(device_, sampler_);
    if (pipe_copy_) SDL_ReleaseGPUGraphicsPipeline(device_, pipe_copy_);
    if (pipe_crt_) SDL_ReleaseGPUGraphicsPipeline(device_, pipe_crt_);
    if (mask_tex_) SDL_ReleaseGPUTexture(device_, mask_tex_);
    if (mask_upload_) SDL_ReleaseGPUTransferBuffer(device_, mask_upload_);
    pipe_crt_ = nullptr;
    mask_tex_ = nullptr;
    mask_upload_ = nullptr;
    mask_extent_ = -1;
    upload_ = nullptr;
    frame_tex_ = nullptr;
    sampler_ = nullptr;
    pipe_copy_ = nullptr;
    frame_w_ = frame_h_ = 0;
    SDL_ReleaseWindowFromGPUDevice(device_, window_);
    SDL_DestroyGPUDevice(device_);
    device_ = nullptr;
}

void Video::close() {
    close_gpu();
    if (texture_) SDL_DestroyTexture(texture_);
    if (renderer_) SDL_DestroyRenderer(renderer_);
    if (window_) SDL_DestroyWindow(window_);
    texture_ = nullptr;
    renderer_ = nullptr;
    window_ = nullptr;
}

double Video::refresh_rate() const {
    const SDL_DisplayID d = SDL_GetDisplayForWindow(window_);
    const SDL_DisplayMode* m = d ? SDL_GetCurrentDisplayMode(d) : nullptr;
    if (!m) return 0.0;
    if (m->refresh_rate_numerator > 0 && m->refresh_rate_denominator > 0)
        return static_cast<double>(m->refresh_rate_numerator) / m->refresh_rate_denominator;
    return m->refresh_rate;
}

bool Video::enable_crt(bool on, std::string* why) {
    if (on && !device_) {
        if (why) *why = "the tube needs the GPU path (--video gpu and a Vulkan device)";
        return false;
    }
    if (on && crt_.params.empty()) {
        if (why) *why = "no tube profile";
        return false;
    }
    crt_on_ = on;
    return true;
}

void Video::present(const jf::machine::Frame& f) {
    if (device_) present_gpu(f);
    else present_renderer(f);
}

bool Video::save_capture(SDL_Surface* s) {
    const std::string path = capture_path_;
    capture_path_.clear();
    // One pixel format for both paths: the same picture gives the same file.
    SDL_Surface* x = s ? SDL_ConvertSurface(s, SDL_PIXELFORMAT_XRGB8888) : nullptr;
    bool ok = x && (ends_with(path, ".bmp") ? SDL_SaveBMP(x, path.c_str()) : SDL_SavePNG(x, path.c_str()));
    if (x) SDL_DestroySurface(x);
    std::fprintf(stderr, "mamr_play: picture %s %s%s\n", ok ? "written to" : "not written:", path.c_str(),
                 ok ? "" : (std::string(" ") + SDL_GetError()).c_str());
    return ok;
}

void Video::present_renderer(const jf::machine::Frame& f) {
    if (!texture_ || tex_w_ != f.width || tex_h_ != f.height) {
        if (texture_) SDL_DestroyTexture(texture_);
        texture_ = SDL_CreateTexture(renderer_, SDL_PIXELFORMAT_XRGB8888, SDL_TEXTUREACCESS_STREAMING,
                                     static_cast<int>(f.width), static_cast<int>(f.height));
        SDL_SetTextureScaleMode(texture_, SDL_SCALEMODE_NEAREST);
        tex_w_ = f.width;
        tex_h_ = f.height;
    }
    SDL_UpdateTexture(texture_, nullptr, f.pixels, static_cast<int>(f.pitch * 4));
    int ww = 0, wh = 0;
    SDL_GetWindowSizeInPixels(window_, &ww, &wh);
    const PictureRect r = picture_rect(scaling, overscan, ww, wh, f.width * f.pixel_aspect.value(), f.height);
    const SDL_FRect dst{static_cast<float>(r.x), static_cast<float>(r.y), static_cast<float>(r.w),
                        static_cast<float>(r.h)};
    SDL_RenderClear(renderer_);
    SDL_RenderTexture(renderer_, texture_, nullptr, &dst);
    if (!capture_path_.empty()) {
        SDL_Surface* s = SDL_RenderReadPixels(renderer_, nullptr);
        save_capture(s);
        if (s) SDL_DestroySurface(s);
    }
    SDL_RenderPresent(renderer_);
}

bool Video::upload_mask(SDL_GPUCommandBuffer* cmd, double extent) {
    tile_ = crt_mask_tile(crt_, extent);
    if (mask_tex_) SDL_ReleaseGPUTexture(device_, mask_tex_);
    if (mask_upload_) SDL_ReleaseGPUTransferBuffer(device_, mask_upload_);
    SDL_GPUTextureCreateInfo ti{};
    ti.type = SDL_GPU_TEXTURETYPE_2D;
    ti.format = SDL_GPU_TEXTUREFORMAT_R8G8B8A8_UNORM;
    ti.usage = SDL_GPU_TEXTUREUSAGE_SAMPLER;
    ti.width = static_cast<Uint32>(tile_.length);
    ti.height = 1;
    ti.layer_count_or_depth = 1;
    ti.num_levels = 1;
    mask_tex_ = SDL_CreateGPUTexture(device_, &ti);
    SDL_GPUTransferBufferCreateInfo bi{};
    bi.usage = SDL_GPU_TRANSFERBUFFERUSAGE_UPLOAD;
    bi.size = static_cast<Uint32>(tile_.rgba.size());
    mask_upload_ = SDL_CreateGPUTransferBuffer(device_, &bi);
    void* map = mask_tex_ && mask_upload_ ? SDL_MapGPUTransferBuffer(device_, mask_upload_, false) : nullptr;
    if (!map) {
        std::fprintf(stderr, "mamr_play: video: mask tile: %s\n", SDL_GetError());
        return false;
    }
    std::memcpy(map, tile_.rgba.data(), tile_.rgba.size());
    SDL_UnmapGPUTransferBuffer(device_, mask_upload_);
    SDL_GPUCopyPass* copy = SDL_BeginGPUCopyPass(cmd);
    SDL_GPUTextureTransferInfo src{};
    src.transfer_buffer = mask_upload_;
    src.pixels_per_row = static_cast<Uint32>(tile_.length);
    src.rows_per_layer = 1;
    SDL_GPUTextureRegion reg{};
    reg.texture = mask_tex_;
    reg.w = static_cast<Uint32>(tile_.length);
    reg.h = 1;
    reg.d = 1;
    SDL_UploadToGPUTexture(copy, &src, &reg, false);
    SDL_EndGPUCopyPass(copy);
    mask_extent_ = extent;
    std::fprintf(stderr, "mamr_play: crt: triad pitch %.2f window pixels, tile %d pixels\n", tile_.period_px,
                 tile_.length);
    return true;
}

void Video::present_gpu(const jf::machine::Frame& f) {
    if (!frame_tex_ || frame_w_ != f.width || frame_h_ != f.height) {
        if (frame_tex_) SDL_ReleaseGPUTexture(device_, frame_tex_);
        if (upload_) SDL_ReleaseGPUTransferBuffer(device_, upload_);
        // XRGB8888 in memory is B, G, R, X: the BGRA texture format.
        SDL_GPUTextureCreateInfo ti{};
        ti.type = SDL_GPU_TEXTURETYPE_2D;
        ti.format = SDL_GPU_TEXTUREFORMAT_B8G8R8A8_UNORM;
        ti.usage = SDL_GPU_TEXTUREUSAGE_SAMPLER;
        ti.width = f.width;
        ti.height = f.height;
        ti.layer_count_or_depth = 1;
        ti.num_levels = 1;
        frame_tex_ = SDL_CreateGPUTexture(device_, &ti);
        SDL_GPUTransferBufferCreateInfo bi{};
        bi.usage = SDL_GPU_TRANSFERBUFFERUSAGE_UPLOAD;
        bi.size = f.width * f.height * 4;
        upload_ = SDL_CreateGPUTransferBuffer(device_, &bi);
        frame_w_ = f.width;
        frame_h_ = f.height;
        if (!frame_tex_ || !upload_) {
            std::fprintf(stderr, "mamr_play: video: frame texture: %s\n", SDL_GetError());
            return;
        }
    }
    if (void* map = SDL_MapGPUTransferBuffer(device_, upload_, true)) {
        auto* dst = static_cast<std::uint8_t*>(map);
        for (jf::machine::u32 y = 0; y < f.height; ++y)
            std::memcpy(dst + static_cast<size_t>(y) * f.width * 4, f.pixels + static_cast<size_t>(y) * f.pitch,
                        static_cast<size_t>(f.width) * 4);
        SDL_UnmapGPUTransferBuffer(device_, upload_);
    }
    SDL_GPUCommandBuffer* cmd = SDL_AcquireGPUCommandBuffer(device_);
    if (!cmd) return;
    SDL_GPUCopyPass* copy = SDL_BeginGPUCopyPass(cmd);
    SDL_GPUTextureTransferInfo src{};
    src.transfer_buffer = upload_;
    src.pixels_per_row = f.width;
    src.rows_per_layer = f.height;
    SDL_GPUTextureRegion reg{};
    reg.texture = frame_tex_;
    reg.w = f.width;
    reg.h = f.height;
    reg.d = 1;
    SDL_UploadToGPUTexture(copy, &src, &reg, true);
    SDL_EndGPUCopyPass(copy);

    SDL_GPUTexture* swap = nullptr;
    Uint32 sw = 0, sh = 0;
    if (!SDL_WaitAndAcquireGPUSwapchainTexture(cmd, window_, &swap, &sw, &sh)) {
        std::fprintf(stderr, "mamr_play: video: swapchain: %s\n", SDL_GetError());
        SDL_CancelGPUCommandBuffer(cmd);
        return;
    }
    // The GPU time counts from here: the wait for the swapchain is the
    // display's, and the upload above runs on the GPU after the submit.
    const Uint64 t1 = SDL_GetTicksNS();
    ScreenUniforms u{};
    CrtUniforms cu{};
    const bool crt = crt_on_ && swap;
    if (swap) {
        const PictureRect r = picture_rect(scaling, overscan, static_cast<int>(sw), static_cast<int>(sh),
                                           f.width * f.pixel_aspect.value(), f.height);
        u.dst[0] = static_cast<float>(r.x);
        u.dst[1] = static_cast<float>(r.y);
        u.dst[2] = static_cast<float>(r.w);
        u.dst[3] = static_cast<float>(r.h);
        u.src[0] = static_cast<float>(f.width);
        u.src[1] = static_cast<float>(f.height);
        if (crt) {
            // The mask tile follows the picture's length along the
            // scanlines; drawn again and uploaded when that changes.
            const double extent = raster_.rotated ? r.h : r.w;
            if (extent != mask_extent_ || !mask_tex_) {
                if (!upload_mask(cmd, extent)) {
                    SDL_CancelGPUCommandBuffer(cmd);
                    return;
                }
            }
            crt_uniforms(crt_, raster_, r.x, r.y, r.w, r.h, f.width, f.height, f.pixel_aspect.value(),
                         nominal_par_, tile_, &cu);
        }
    }
    auto draw = [&](SDL_GPUTexture* target) {
        SDL_GPUColorTargetInfo ci{};
        ci.texture = target;
        ci.clear_color = SDL_FColor{0.0f, 0.0f, 0.0f, 1.0f};
        ci.load_op = SDL_GPU_LOADOP_CLEAR;
        ci.store_op = SDL_GPU_STOREOP_STORE;
        SDL_GPURenderPass* pass = SDL_BeginGPURenderPass(cmd, &ci, 1, nullptr);
        if (crt) {
            SDL_BindGPUGraphicsPipeline(pass, pipe_crt_);
            const SDL_GPUTextureSamplerBinding tb[2] = {{frame_tex_, sampler_}, {mask_tex_, sampler_}};
            SDL_BindGPUFragmentSamplers(pass, 0, tb, 2);
            SDL_PushGPUFragmentUniformData(cmd, 0, &cu, sizeof(cu));
        } else {
            SDL_BindGPUGraphicsPipeline(pass, pipe_copy_);
            SDL_GPUTextureSamplerBinding tb{frame_tex_, sampler_};
            SDL_BindGPUFragmentSamplers(pass, 0, &tb, 1);
            SDL_PushGPUFragmentUniformData(cmd, 0, &u, sizeof(u));
        }
        SDL_DrawGPUPrimitives(pass, 3, 1, 0, 0);
        SDL_EndGPURenderPass(pass);
    };
    if (swap) draw(swap);

    // The capture: the same pass once more into a texture of the
    // swapchain's size and format, downloaded after the fence.
    SDL_GPUTexture* cap = nullptr;
    SDL_GPUTransferBuffer* down = nullptr;
    if (swap && !capture_path_.empty()) {
        SDL_GPUTextureCreateInfo ti{};
        ti.type = SDL_GPU_TEXTURETYPE_2D;
        ti.format = target_format_;
        ti.usage = SDL_GPU_TEXTUREUSAGE_COLOR_TARGET;
        ti.width = sw;
        ti.height = sh;
        ti.layer_count_or_depth = 1;
        ti.num_levels = 1;
        cap = SDL_CreateGPUTexture(device_, &ti);
        SDL_GPUTransferBufferCreateInfo bi{};
        bi.usage = SDL_GPU_TRANSFERBUFFERUSAGE_DOWNLOAD;
        bi.size = sw * sh * 4;
        down = SDL_CreateGPUTransferBuffer(device_, &bi);
        if (cap && down) {
            draw(cap);
            SDL_GPUCopyPass* cp = SDL_BeginGPUCopyPass(cmd);
            SDL_GPUTextureRegion cr{};
            cr.texture = cap;
            cr.w = sw;
            cr.h = sh;
            cr.d = 1;
            SDL_GPUTextureTransferInfo dt{};
            dt.transfer_buffer = down;
            dt.pixels_per_row = sw;
            dt.rows_per_layer = sh;
            SDL_DownloadFromGPUTexture(cp, &cr, &dt);
            SDL_EndGPUCopyPass(cp);
        }
    }

    if (gpu_timing_ || down) {
        SDL_GPUFence* fence = SDL_SubmitGPUCommandBufferAndAcquireFence(cmd);
        if (fence) {
            SDL_WaitForGPUFences(device_, true, &fence, 1);
            SDL_ReleaseGPUFence(device_, fence);
        }
        if (gpu_timing_ && swap) {
            const double ms = static_cast<double>(SDL_GetTicksNS() - t1) / 1e6;
            gpu_sum_ += ms;
            gpu_max_ = std::max(gpu_max_, ms);
            ++gpu_n_;
        }
    } else {
        SDL_SubmitGPUCommandBuffer(cmd);
    }
    if (down) {
        SDL_PixelFormat pf = SDL_PIXELFORMAT_UNKNOWN;
        if (target_format_ == SDL_GPU_TEXTUREFORMAT_B8G8R8A8_UNORM) pf = SDL_PIXELFORMAT_BGRA32;
        else if (target_format_ == SDL_GPU_TEXTUREFORMAT_R8G8B8A8_UNORM) pf = SDL_PIXELFORMAT_RGBA32;
        void* map = cap ? SDL_MapGPUTransferBuffer(device_, down, false) : nullptr;
        if (map && pf != SDL_PIXELFORMAT_UNKNOWN) {
            SDL_Surface* s = SDL_CreateSurfaceFrom(static_cast<int>(sw), static_cast<int>(sh), pf, map,
                                                   static_cast<int>(sw * 4));
            save_capture(s);
            if (s) SDL_DestroySurface(s);
        } else {
            capture_path_.clear();
            std::fprintf(stderr, "mamr_play: picture not written (swapchain format %d)\n",
                         static_cast<int>(target_format_));
        }
        if (map) SDL_UnmapGPUTransferBuffer(device_, down);
    }
    if (down) SDL_ReleaseGPUTransferBuffer(device_, down);
    if (cap) SDL_ReleaseGPUTexture(device_, cap);
}

} // namespace jf::play
