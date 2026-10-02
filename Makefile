ROOT := $(shell pwd)
OPUS_PREFIX := $(ROOT)/build/opus
OPUS_CFLAGS := -I$(OPUS_PREFIX)/include
OPUS_LIBS   := -L$(OPUS_PREFIX)/lib -lopus -lm

CC      ?= cc
CFLAGS  ?= -O2 -Wall -Wextra -Wpedantic

.PHONY: build tools clean

build:
	./scripts/01_build_opus.sh

tools: build/encode_raw build/decode_raw

build/encode_raw: scripts/encode_raw.c
	@mkdir -p build
	$(CC) $(CFLAGS) $(OPUS_CFLAGS) $< -o $@ $(OPUS_LIBS)

build/decode_raw: scripts/decode_raw.c
	@mkdir -p build
	$(CC) $(CFLAGS) $(OPUS_CFLAGS) $< -o $@ $(OPUS_LIBS)

clean:
	rm -rf opus build/opus build/encode_raw build/decode_raw