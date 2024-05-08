.PHONY: all clean

PREFIX  := riscv32-unknown-elf
CC      := $(PREFIX)-gcc
OBJCOPY := $(PREFIX)-objcopy

SRC := $(wildcard ./*.s)
OBJ := $(SRC:%.s=%.elf)
BIN := $(SRC:%.s=%.bin)
CFLAGS := -mabi=ilp32 -march=rv32i -nostdlib
LDFLAGS := --section-start=.text=0x00000000
OBJCOPY_FLAGS := -v -O binary --only-section=.text

all: $(OBJ) $(BIN)
%.elf: %.s
	$(CC) $(CFLAGS) -Wl,$(LDFLAGS) $< -o $@
%.bin: %.elf
	$(OBJCOPY) $(OBJCOPY_FLAGS) $< $@
clean:
	rm -vf *.elf *.bin

