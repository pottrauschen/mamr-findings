// The picture of the front end (docs/frontend.md section 6): one window,
// two ways to draw into it. The GPU path (SDL's GPU API, Vulkan with
// SPIR-V shaders) uploads the frame to a texture and draws it with a
// shader into the swapchain; the renderer path (SDL_Renderer, nearest
// scaling) is the fallback where no Vulkan device can be had. Both place
// the picture in the same rectangle (scaling mode and pixel shape), and
// the GPU path's pass-through shader reproduces the renderer path byte
// for byte (a test of the unpublished front end).
#pragma once
#include "runtime/machine/machine.h"
#include "play_crt.h"

#include <SDL3/SDL.h>

#include <string>

namespace jf::play {

// Where the picture goes in a window of ww x wh pixels: x, y, w, h (may
// reach outside the window in overscan mode).
struct PictureRect {
    double x = 0, y = 0, w = 0, h = 0;
};
// scaling: integer | aspect (alias fit) | stretch | overscan.
PictureRect picture_rect(const std::string& scaling, double overscan, int ww, int wh, double cw, double ch);

class Video {
public:
    // backend: "gpu" (falls back to the renderer when the GPU path
    // cannot start, with the reason on stderr) or "renderer".
    bool open(const std::string& title, int w, int h, bool fullscreen, bool want_vsync, const std::string& backend,
              std::string* error);
    void close();
    // The display's refresh rate in Hz, 0 when unknown.
    double refresh_rate() const;
    void present(const jf::machine::Frame& f);

    // Write the next presented picture (the whole window, as shown) to a
    // PNG or BMP file (by the extension); the result on stderr.
    void capture_next(const std::string& path) { capture_path_ = path; }
    // Wait for the GPU after each frame and keep the time from the
    // submit to the fence (the cost of the upload and the shader; GPU
    // path only).
    void set_gpu_timing(bool on) { gpu_timing_ = on; }
    double gpu_ms_mean() const { return gpu_n_ ? gpu_sum_ / static_cast<double>(gpu_n_) : 0.0; }
    double gpu_ms_max() const { return gpu_max_; }

    // The tube (play_crt.h, glsl/crt.frag): the profile and the
    // machine's raster, and whether it is drawn (GPU path only). False
    // with a message when it cannot be switched on.
    void set_crt(const CrtProfile& profile, const CrtRaster& raster, double nominal_par) {
        crt_ = profile;
        raster_ = raster;
        nominal_par_ = nominal_par;
        mask_extent_ = -1;
    }
    bool enable_crt(bool on, std::string* why);
    bool crt_enabled() const { return crt_on_; }

    SDL_Window* window() const { return window_; }
    bool vsync() const { return vsync_; }
    const char* backend() const { return device_ ? "gpu" : "renderer"; }
    std::string scaling = "integer";
    double overscan = 0.08; // overscan mode: the largest part of the picture that may be cut off

private:
    bool open_gpu(bool want_vsync, std::string* why);
    void close_gpu();
    bool open_renderer(bool want_vsync, std::string* error);
    void present_gpu(const jf::machine::Frame& f);
    bool upload_mask(SDL_GPUCommandBuffer* cmd, double extent);
    void present_renderer(const jf::machine::Frame& f);
    bool save_capture(SDL_Surface* s);

    SDL_Window* window_ = nullptr;
    bool vsync_ = true;
    std::string capture_path_;

    // Renderer path.
    SDL_Renderer* renderer_ = nullptr;
    SDL_Texture* texture_ = nullptr;
    jf::machine::u32 tex_w_ = 0, tex_h_ = 0;

    // GPU path.
    SDL_GPUDevice* device_ = nullptr;
    SDL_GPUGraphicsPipeline* pipe_copy_ = nullptr;
    SDL_GPUGraphicsPipeline* pipe_crt_ = nullptr;
    SDL_GPUTextureFormat target_format_ = SDL_GPU_TEXTUREFORMAT_INVALID;
    SDL_GPUSampler* sampler_ = nullptr;
    SDL_GPUTexture* frame_tex_ = nullptr;
    SDL_GPUTransferBuffer* upload_ = nullptr;
    jf::machine::u32 frame_w_ = 0, frame_h_ = 0;
    CrtProfile crt_;
    CrtRaster raster_;
    bool crt_on_ = false;
    double nominal_par_ = 1;
    CrtMaskTile tile_;
    double mask_extent_ = -1; // the line extent the tile was drawn for
    SDL_GPUTexture* mask_tex_ = nullptr;
    SDL_GPUTransferBuffer* mask_upload_ = nullptr;
    bool gpu_timing_ = false;
    double gpu_sum_ = 0, gpu_max_ = 0;
    jf::machine::u64 gpu_n_ = 0;
};

} // namespace jf::play
