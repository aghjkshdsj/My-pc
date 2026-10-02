/* Guest-origin GL shader diagnostic. Readback is diagnostic-only, not scanout. */
#define GL_GLEXT_PROTOTYPES
#include <SDL2/SDL.h>
#include <SDL2/SDL_opengl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/utsname.h>
#include "renderer_classification.h"

static GLuint shader(GLenum type, const char *source) {
    GLuint result = glCreateShader(type);
    glShaderSource(result, 1, &source, NULL);
    glCompileShader(result);
    GLint ok;
    glGetShaderiv(result, GL_COMPILE_STATUS, &ok);
    if (!ok) { char log[4096]; glGetShaderInfoLog(result, sizeof(log), NULL, log); fprintf(stderr, "%s\n", log); exit(3); }
    return result;
}
static int software(const char *renderer) {
    return mpc_renderer_is_software(renderer);
}
static int draw_and_check(GLuint program, unsigned phase, unsigned char *pixels) {
    glUniform1ui(glGetUniformLocation(program, "phase"), phase);
    glDrawArrays(GL_TRIANGLES, 0, 3);
    glFinish();
    glReadPixels(0, 0, 1280, 720, GL_RGBA, GL_UNSIGNED_BYTE, pixels);
    int mismatches = 0;
    for (unsigned y = 0; y < 720; ++y) for (unsigned x = 0; x < 1280; ++x) {
        const unsigned char *p = pixels + (y * 1280 + x) * 4;
        mismatches += p[0] != ((x + phase) & 255) || p[1] != ((y + phase) & 255) ||
                      p[2] != ((0xa5 ^ phase) & 255) || p[3] != 255;
    }
    return mismatches;
}
int main(int argc, char **argv) {
    int diagnostic = argc == 2 && !strcmp(argv[1], "--allow-software-diagnostic");
    if (SDL_Init(SDL_INIT_VIDEO)) { fprintf(stderr, "%s\n", SDL_GetError()); return 2; }
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
    SDL_GL_SetAttribute(SDL_GL_RED_SIZE, 8); SDL_GL_SetAttribute(SDL_GL_GREEN_SIZE, 8);
    SDL_GL_SetAttribute(SDL_GL_BLUE_SIZE, 8); SDL_GL_SetAttribute(SDL_GL_ALPHA_SIZE, 8);
    SDL_Window *window = SDL_CreateWindow("My-pc guest GL gate", SDL_WINDOWPOS_UNDEFINED,
        SDL_WINDOWPOS_UNDEFINED, 1280, 720, SDL_WINDOW_OPENGL);
    SDL_GLContext context = window ? SDL_GL_CreateContext(window) : NULL;
    if (!context) { fprintf(stderr, "%s\n", SDL_GetError()); return 2; }
    const char *renderer = (const char *)glGetString(GL_RENDERER);
    const char *version = (const char *)glGetString(GL_VERSION);
    const char *vendor = (const char *)glGetString(GL_VENDOR);
    int fallback = software(renderer);
    if (fallback && !diagnostic) {
        printf("MPC_GL_REJECTED software_renderer=%s\n", renderer ? renderer : "unknown");
        return 20;
    }
    GLuint vs = shader(GL_VERTEX_SHADER, "#version 330 core\nvoid main(){vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);gl_Position=vec4(p*2.0-1.0,0,1);}");
    GLuint fs = shader(GL_FRAGMENT_SHADER, "#version 330 core\nuniform uint phase;out vec4 color;void main(){uvec2 p=uvec2(gl_FragCoord.xy);color=vec4(vec3(uvec3((p.x+phase)&255u,(p.y+phase)&255u,(165u^phase)&255u))/255.0,1.0);}");
    GLuint program = glCreateProgram();
    glAttachShader(program, vs); glAttachShader(program, fs); glLinkProgram(program);
    GLint linked; glGetProgramiv(program, GL_LINK_STATUS, &linked);
    if (!linked) return 3;
    glUseProgram(program);
    GLuint vao, texture, fbo;
    glGenVertexArrays(1, &vao); glBindVertexArray(vao);
    glGenTextures(1, &texture); glBindTexture(GL_TEXTURE_2D, texture);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, 1280, 720, 0, GL_RGBA, GL_UNSIGNED_BYTE, NULL);
    glGenFramebuffers(1, &fbo); glBindFramebuffer(GL_FRAMEBUFFER, fbo);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, texture, 0);
    if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) return 4;
    glViewport(0, 0, 1280, 720);
    glDisable(GL_DITHER); glDisable(GL_BLEND); glDisable(GL_MULTISAMPLE); glDisable(GL_FRAMEBUFFER_SRGB);
    glPixelStorei(GL_PACK_ALIGNMENT, 1);
    unsigned char *pixels = malloc(1280 * 720 * 4);
    if (!pixels) return 5;
    int mismatches = draw_and_check(program, 0, pixels) + draw_and_check(program, 41, pixels);
    GLenum error = glGetError();
    // Moving guest-origin content for a later host presentation counter/trace.
    // This is not game FPS, and this guest receipt alone cannot prove Metal.
    for (unsigned frame = 0; frame < 120; ++frame) {
        glBindFramebuffer(GL_FRAMEBUFFER, fbo);
        glUniform1ui(glGetUniformLocation(program, "phase"), frame);
        glDrawArrays(GL_TRIANGLES, 0, 3);
        glBindFramebuffer(GL_READ_FRAMEBUFFER, fbo);
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, 0);
        glBlitFramebuffer(0, 0, 1280, 720, 0, 0, 1280, 720, GL_COLOR_BUFFER_BIT, GL_NEAREST);
        SDL_GL_SwapWindow(window);
        SDL_PumpEvents();
    }
    glFinish();
    error = error ? error : glGetError();
    struct utsname machine; if (uname(&machine)) return 6;
    printf("MPC_GL_DIAGNOSTIC machine=%s renderer=%s vendor=%s version=%s software=%d pixels_checked=%u shader_phases=2 mismatches=%d gl_error=%u submitted_frames=120 metal_host_verified=0 game_fps_verified=0\n",
           machine.machine, renderer, vendor, version, fallback, 1280u * 720u * 2u, mismatches, error);
    free(pixels);
    glDeleteFramebuffers(1, &fbo); glDeleteTextures(1, &texture); glDeleteVertexArrays(1, &vao);
    glDeleteProgram(program); glDeleteShader(vs); glDeleteShader(fs);
    SDL_GL_DeleteContext(context); SDL_DestroyWindow(window); SDL_Quit();
    return mismatches || error ? 7 : 0;
}
