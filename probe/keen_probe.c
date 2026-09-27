#include <SDL.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define PATH_LIMIT 512

static volatile unsigned long audio_callbacks;
static unsigned long audio_phase;
static int audio_audible_requested;
static short audio_tone[50];

static int fpu_test(void)
{
    volatile double a = 1.5;
    volatile double b = 2.25;
    volatile double result = a * b + 0.625;
    return result > 3.999 && result < 4.001;
}

static void audio_fill(void *unused, Uint8 *stream, int length)
{
    int i;
    (void)unused;
    for (i = 0; i + 1 < length; i += 2) {
        Uint16 sample = 0;
        if (audio_audible_requested && audio_phase < 4410)
            sample = (Uint16)audio_tone[audio_phase % 50];
        stream[i] = (Uint8)(sample >> 8);
        stream[i + 1] = (Uint8)sample;
        ++audio_phase;
    }
    if (i < length)
        stream[i] = 0;
    ++audio_callbacks;
}

static int valid_id(const char *id)
{
    const unsigned char *p = (const unsigned char *)id;
    if (!*p || strlen(id) > 64)
        return 0;
    for (; *p; ++p) {
        if (!((*p >= 'a' && *p <= 'z') || (*p >= 'A' && *p <= 'Z') ||
              (*p >= '0' && *p <= '9') || *p == '-' || *p == '_' || *p == '.'))
            return 0;
    }
    return 1;
}

static int result_path(char *path, size_t size, const char *dir,
                       const char *run, const char *suffix)
{
    size_t length = strlen(dir);
    const char *separator = length && (dir[length - 1] == ':' || dir[length - 1] == '/')
                            ? "" : "/";
    int n = snprintf(path, size, "%s%s%s.%s", dir, separator, run, suffix);
    return n > 0 && (size_t)n < size;
}

static int record(const char *dir, const char *run, const char *suffix,
                  const char *mode, const char *message)
{
    char path[PATH_LIMIT];
    FILE *file;
    if (!result_path(path, sizeof(path), dir, run, suffix))
        return 0;
    file = fopen(path, mode);
    if (!file)
        return 0;
    if (fputs(message, file) == EOF || fflush(file) != 0) {
        fclose(file);
        return 0;
    }
    return fclose(file) == 0;
}

static int record_atomic(const char *dir, const char *run,
                         const char *suffix, const char *message)
{
    char temporary[PATH_LIMIT];
    char final[PATH_LIMIT];
    char temp_suffix[32];
    if (snprintf(temp_suffix, sizeof(temp_suffix), "%s.tmp", suffix) >=
        (int)sizeof(temp_suffix) ||
        !result_path(temporary, sizeof(temporary), dir, run, temp_suffix) ||
        !result_path(final, sizeof(final), dir, run, suffix))
        return 0;
    if (!record(dir, run, temp_suffix, "wb", message))
        return 0;
    if (rename(temporary, final) != 0) {
        remove(temporary);
        return 0;
    }
    return 1;
}

static void log_sdl(const char *dir, const char *run, const char *build,
                    const char *stage)
{
    char message[512];
    char error[256];
    const char *source = SDL_GetError();
    size_t i;
    snprintf(error, sizeof(error), "%s", source ? source : "");
    for (i = 0; error[i]; ++i) {
        if (error[i] == '\n' || error[i] == '\r')
            error[i] = ' ';
    }
    snprintf(message, sizeof(message), "run_id=%s build_id=%s stage=%s sdl_error=%s\n",
             run, build, stage, error[0] ? error : "none");
    record(dir, run, "progress", "ab", message);
}

static int file_test(const char *dir, const char *run)
{
    static const char payload[] = "keen-probe-file-v1\n";
    char path[PATH_LIMIT];
    char content[sizeof(payload)];
    FILE *file;
    int ok;
    if (!result_path(path, sizeof(path), dir, run, "roundtrip"))
        return 0;
    file = fopen(path, "wb");
    if (!file)
        return 0;
    ok = fwrite(payload, 1, sizeof(payload), file) == sizeof(payload);
    ok = fclose(file) == 0 && ok;
    if (!ok)
        return 0;
    file = fopen(path, "rb");
    if (!file)
        return 0;
    ok = fread(content, 1, sizeof(content), file) == sizeof(content);
    ok = fclose(file) == 0 && ok;
    return ok && memcmp(payload, content, sizeof(payload)) == 0;
}

static int graphics_test(const char *dir, const char *run, const char *build)
{
    SDL_Surface *screen;
    SDL_Color colors[256];
    int x, y, i, palette_result, flip_result;
    char message[512];
    snprintf(message, sizeof(message),
             "run_id=%s build_id=%s video_mode_ok_window=%d video_mode_ok_fullscreen=%d\n",
             run, build, SDL_VideoModeOK(320, 200, 8, SDL_SWSURFACE),
             SDL_VideoModeOK(320, 200, 8, SDL_FULLSCREEN | SDL_HWPALETTE));
    record(dir, run, "progress", "ab", message);
    SDL_ClearError();
    screen = SDL_SetVideoMode(320, 200, 8,
                              SDL_SWSURFACE | SDL_FULLSCREEN | SDL_HWPALETTE);
    if (!screen) {
        log_sdl(dir, run, build, "set_video_mode_failed");
        return 0;
    }
    snprintf(message, sizeof(message),
             "run_id=%s build_id=%s video_surface_width=%d height=%d depth=%d flags=0x%08lx pitch=%u\n",
             run, build, screen->w, screen->h,
             screen->format ? screen->format->BitsPerPixel : 0,
             (unsigned long)screen->flags, (unsigned int)screen->pitch);
    record(dir, run, "progress", "ab", message);
    if (!screen->format || screen->w != 320 || screen->h != 200 ||
        screen->format->BitsPerPixel != 8 ||
        !(screen->flags & SDL_FULLSCREEN) ||
        !(screen->flags & SDL_HWPALETTE)) {
        log_sdl(dir, run, build, "video_surface_mismatch");
        return 0;
    }
    for (i = 0; i < 256; ++i) {
        colors[i].r = (Uint8)i;
        colors[i].g = (Uint8)(255 - i);
        colors[i].b = (Uint8)(i / 2);
        colors[i].unused = 0;
    }
    SDL_ClearError();
    palette_result = SDL_SetColors(screen, colors, 0, 256);
    snprintf(message, sizeof(message),
             "run_id=%s build_id=%s set_colors_return=%d\n",
             run, build, palette_result);
    record(dir, run, "progress", "ab", message);
    if (palette_result != 1) {
        log_sdl(dir, run, build, "set_colors_failed");
        return 0;
    }
    SDL_ClearError();
    if (SDL_MUSTLOCK(screen) && SDL_LockSurface(screen) != 0) {
        log_sdl(dir, run, build, "lock_surface_failed");
        return 0;
    }
    for (y = 0; y < 200; ++y) {
        Uint8 *row = (Uint8 *)screen->pixels + y * screen->pitch;
        for (x = 0; x < 320; ++x)
            row[x] = (Uint8)((x / 8 + y / 8) & 255);
    }
    if (SDL_MUSTLOCK(screen))
        SDL_UnlockSurface(screen);
    SDL_ClearError();
    flip_result = SDL_Flip(screen);
    if (flip_result != 0)
        log_sdl(dir, run, build, "flip_failed");
    return flip_result == 0;
}

int main(int argc, char **argv)
{
    const char *run = NULL, *build = NULL, *dir = NULL;
    int interactive = 0, i, video_ok = 0, timer_ok = 0, audio_open = 0;
    int file_ok, fpu_ok, graphics_ok = 0, input_seen = 0, audio_progress = 0;
    int started, elapsed_ok = 0, success;
    Uint32 begin = 0, now, last_progress = 0;
    unsigned long callbacks = 0;
    SDL_AudioSpec wanted, obtained;
    SDL_Event event;
    char message[1024];
    char driver[128];

    for (i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--run-id") == 0 && i + 1 < argc)
            run = argv[++i];
        else if (strcmp(argv[i], "--build-id") == 0 && i + 1 < argc)
            build = argv[++i];
        else if (strcmp(argv[i], "--result-dir") == 0 && i + 1 < argc)
            dir = argv[++i];
        else if (strcmp(argv[i], "--interactive") == 0)
            interactive = 1;
        else if (strcmp(argv[i], "--audible") == 0)
            audio_audible_requested = 1;
        else {
            fprintf(stderr, "invalid argument: %s\n", argv[i]);
            return 2;
        }
    }
    if (!run || !build || !dir || !valid_id(run) || !valid_id(build)) {
        fputs("usage: keen-probe --run-id ID --build-id ID --result-dir DIR [--interactive] [--audible]\n", stderr);
        return 2;
    }

    if (audio_audible_requested) {
        for (i = 0; i < 50; ++i)
            audio_tone[i] = (short)(1200.0 * sin(6.283185307179586 * i / 50.0));
    }

    snprintf(message, sizeof(message),
             "run_id=%s\nbuild_id=%s\nmode=%s\naudio_signal=%s\nstate=started\n",
             run, build, interactive ? "interactive" : "automatic",
             audio_audible_requested ? "audible" : "silent");
    started = record_atomic(dir, run, "start", message);
    if (!started) {
        fputs("could not write start record\n", stderr);
        return 3;
    }
    record(dir, run, "progress", "wb", message);
    file_ok = file_test(dir, run);
    fpu_ok = fpu_test();
    snprintf(message, sizeof(message), "run_id=%s build_id=%s file_roundtrip=%s fpu=%s\n",
             run, build, file_ok ? "pass" : "fail", fpu_ok ? "pass" : "fail");
    record(dir, run, "progress", "ab", message);

    SDL_ClearError();
    if (SDL_Init(0) == 0) {
        SDL_ClearError();
        timer_ok = SDL_InitSubSystem(SDL_INIT_TIMER) == 0;
        if (!timer_ok)
            log_sdl(dir, run, build, "timer_init_failed");
        SDL_ClearError();
        video_ok = SDL_InitSubSystem(SDL_INIT_VIDEO) == 0;
        if (!video_ok)
            log_sdl(dir, run, build, "video_init_failed");
        if (video_ok)
            graphics_ok = graphics_test(dir, run, build);
        if (video_ok) {
            snprintf(message, sizeof(message), "run_id=%s build_id=%s video_driver=%s\n",
                     run, build, SDL_VideoDriverName(driver, sizeof(driver)) ? driver : "unknown");
            record(dir, run, "progress", "ab", message);
        }
        SDL_ClearError();
        if (SDL_InitSubSystem(SDL_INIT_AUDIO) == 0) {
            snprintf(message, sizeof(message), "run_id=%s build_id=%s audio_driver=%s\n",
                     run, build, SDL_AudioDriverName(driver, sizeof(driver)) ? driver : "unknown");
            record(dir, run, "progress", "ab", message);
            memset(&wanted, 0, sizeof(wanted));
            wanted.freq = 22050;
            wanted.format = AUDIO_S16SYS;
            wanted.channels = 1;
            wanted.samples = 512;
            wanted.callback = audio_fill;
            snprintf(message, sizeof(message),
                     "run_id=%s build_id=%s audio_requested_freq=%d format=0x%04x channels=%u samples=%u\n",
                     run, build, wanted.freq, wanted.format,
                     (unsigned int)wanted.channels, (unsigned int)wanted.samples);
            record(dir, run, "progress", "ab", message);
            SDL_ClearError();
            if (SDL_OpenAudio(&wanted, &obtained) == 0) {
                snprintf(message, sizeof(message),
                         "run_id=%s build_id=%s audio_obtained_freq=%d format=0x%04x channels=%u samples=%u size=%lu\n",
                         run, build, obtained.freq, obtained.format,
                         (unsigned int)obtained.channels, (unsigned int)obtained.samples,
                         (unsigned long)obtained.size);
                record(dir, run, "progress", "ab", message);
                if (obtained.format == AUDIO_S16SYS && obtained.channels == 1) {
                    audio_open = 1;
                    SDL_PauseAudio(0);
                } else {
                    log_sdl(dir, run, build, "audio_spec_mismatch");
                    SDL_CloseAudio();
                }
            } else {
                log_sdl(dir, run, build, "open_audio_failed");
            }
        } else {
            log_sdl(dir, run, build, "audio_init_failed");
        }
        if (video_ok) {
            SDL_InitSubSystem(SDL_INIT_JOYSTICK);
            SDL_JoystickEventState(SDL_ENABLE);
        }
        if (timer_ok) {
            begin = SDL_GetTicks();
            last_progress = begin;
            do {
                while (SDL_PollEvent(&event)) {
                    if (event.type == SDL_KEYDOWN || event.type == SDL_MOUSEBUTTONDOWN ||
                        event.type == SDL_JOYBUTTONDOWN || event.type == SDL_JOYAXISMOTION)
                        input_seen = 1;
                }
                now = SDL_GetTicks();
                if (now - last_progress >= 1000) {
                    snprintf(message, sizeof(message),
                             "run_id=%s build_id=%s elapsed_ms=%lu input_seen=%d audio_callbacks=%lu\n",
                             run, build, (unsigned long)(now - begin), input_seen,
                             audio_callbacks);
                    record(dir, run, "progress", "ab", message);
                    last_progress = now;
                }
                SDL_Delay(20);
            } while (now - begin < (interactive ? 15000UL : 4000UL));
            elapsed_ok = SDL_GetTicks() - begin >= (interactive ? 15000UL : 4000UL);
        }
        if (audio_open) {
            SDL_LockAudio();
            callbacks = audio_callbacks;
            SDL_UnlockAudio();
            audio_progress = callbacks > 0;
            SDL_CloseAudio();
        }
        SDL_Quit();
    } else {
        log_sdl(dir, run, build, "sdl_init_failed");
    }
    success = file_ok && fpu_ok && graphics_ok && elapsed_ok && audio_progress &&
              (!interactive || input_seen);
    snprintf(message, sizeof(message),
             "run_id=%s\nbuild_id=%s\nmode=%s\nstate=finished\nresult=%s\n"
             "file_roundtrip=%s\nfpu_arithmetic=%s\ngraphics_320x200_8bpp=%s\ntimer_elapsed=%s\n"
             "input_subsystem=%s\nhuman_input=%s\naudio_callback=%s\n"
             "audio_signal=%s\naudio_audible=unverified\naudio_callbacks=%lu\n",
             run, build, interactive ? "interactive" : "automatic",
             success ? "pass" : "fail", file_ok ? "pass" : "fail",
             fpu_ok ? "pass" : "fail",
             graphics_ok ? "pass" : "fail", elapsed_ok ? "pass" : "fail",
             video_ok ? "initialized" : "failed", input_seen ? "seen" : "not_seen",
             audio_progress ? "pass" : "fail",
             audio_audible_requested ? "audible" : "silent", callbacks);
    if (!record_atomic(dir, run, "result", message)) {
        fputs("could not write final result\n", stderr);
        return 3;
    }
    return success ? 0 : 1;
}
