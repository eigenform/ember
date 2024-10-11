
.section .text
.global _start
_start:
	nop

.balign 32
_direct_call:
	call _direct_call_tgt

.balign 32
_direct_jump:
	jal x0, _indirect_call

.balign 32
_indirect_call:
	la x6, _indirect_call_tgt
	jalr x1, x6, 0

.balign 32
_indirect_jump:
	la x6, _direct_jump_end
	jalr x0, x6, 0

.balign 32
_direct_jump_end:
	jal x0, _end

.balign 32
_direct_call_tgt:
	ret

.balign 32
_indirect_call_tgt:
	ret

.balign 32
_end:
	nop
	nop
	nop
	nop
	nop
	nop
	nop
	ebreak

