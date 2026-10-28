# aresref is built inside the ares source tree: the ares top-level
# CMakeLists.txt (with patches/ares/0001-build-without-gui.patch applied) adds
# this directory when ARESREF_SOURCE_DIR is set. Use build_aresref.sh.
add_executable(aresref aresref.cpp)
target_include_directories(aresref PRIVATE ${CMAKE_SOURCE_DIR} ${CMAKE_SOURCE_DIR}/ares)
target_compile_definitions(aresref PRIVATE MIA_LIBRARY)
target_link_libraries(aresref PRIVATE ares::ares ares::mia ares::nall)
# mia looks up the cartridge database next to the executable.
add_custom_command(TARGET aresref POST_BUILD
  COMMAND ${CMAKE_COMMAND} -E copy_directory ${CMAKE_SOURCE_DIR}/mia/Database $<TARGET_FILE_DIR:aresref>/Database)
