/* encode_raw.c — raw PCM (48k mono s16le) -> Opus packets in [u32 len][bytes] format */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <opus/opus.h>

#define SAMPLE_RATE 48000
#define CHANNELS    1

static void die(const char *msg) {
    fprintf(stderr, "encode_raw: %s\n", msg);
    exit(1);
}

static void write_u32le(FILE *f, uint32_t v) {
    unsigned char b[4] = { v & 0xff, (v>>8)&0xff, (v>>16)&0xff, (v>>24)&0xff };
    if (fwrite(b, 1, 4, f) != 4) die("short write (len)");
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr,
            "usage: %s <in.raw> <out.opusraw> [--bitrate N] [--frame-ms N] [--mode voip|audio|lowdelay]\n",
            argv[0]);
        return 2;
    }
    const char *in_path  = argv[1];
    const char *out_path = argv[2];

    int bitrate   = 64000;
    int frame_ms  = 20;
    const char *mode = "audio";
    int application = OPUS_APPLICATION_AUDIO;

    for (int i = 3; i < argc; i++) {
        if (!strcmp(argv[i], "--bitrate") && i+1 < argc)  bitrate  = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--frame-ms") && i+1 < argc) frame_ms = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--mode") && i+1 < argc) mode = argv[++i];
        else die("unknown argument");
    }

    if      (!strcmp(mode, "voip"))     application = OPUS_APPLICATION_VOIP;
    else if (!strcmp(mode, "audio"))    application = OPUS_APPLICATION_AUDIO;
    else if (!strcmp(mode, "lowdelay")) application = OPUS_APPLICATION_RESTRICTED_LOWDELAY;
    else die("--mode must be voip|audio|lowdelay");

    int frame_size = SAMPLE_RATE * frame_ms / 1000;

    int err = OPUS_OK;
    OpusEncoder *enc = opus_encoder_create(SAMPLE_RATE, CHANNELS, application, &err);
    if (err != OPUS_OK) die(opus_strerror(err));

    opus_encoder_ctl(enc, OPUS_SET_BITRATE(bitrate));
    opus_encoder_ctl(enc, OPUS_SET_VBR(1));
    opus_encoder_ctl(enc, OPUS_SET_COMPLEXITY(10));

    FILE *fin  = fopen(in_path, "rb");
    if (!fin)  die("cannot open input");
    FILE *fout = fopen(out_path, "wb");
    if (!fout) die("cannot open output");

    /* Reuse one buffer for the PCM frame; libopus does not modify it. */
    opus_int16 *pcm = malloc(sizeof(opus_int16) * frame_size * CHANNELS);
    unsigned char outbuf[1500];
    if (!pcm) die("oom");

    unsigned long long frame_count = 0;
    unsigned long long total_bytes = 0;

    for (;;) {
        size_t n = fread(pcm, sizeof(opus_int16) * CHANNELS, frame_size, fin);
        if (n == 0) break;

        if (n < (size_t)frame_size) {
            memset(pcm + n * CHANNELS, 0, sizeof(opus_int16) * (frame_size - n) * CHANNELS);
        }

        int nb = opus_encode(enc, pcm, frame_size, outbuf, sizeof(outbuf));
        if (nb < 0) die(opus_strerror(nb));

        write_u32le(fout, (uint32_t)nb);
        if (fwrite(outbuf, 1, nb, fout) != (size_t)nb) die("short write (packet)");

        frame_count++;
        total_bytes += nb;
    }

    fprintf(stderr, "encode_raw: %llu frames, %llu packet bytes, bitrate=%d, frame_ms=%d, mode=%s\n",
            frame_count, total_bytes, bitrate, frame_ms, mode);

    free(pcm);
    fclose(fin);
    fclose(fout);
    opus_encoder_destroy(enc);
    return 0;
}