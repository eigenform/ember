
.section .text
.global _start
_start:
	nop

_direct_call:
	call _direct_call_tgt

_indirect_call:
	la x6, _indirect_call_tgt
	jalr x1, x6, 0
	jalr x1, x1, 0

_indirect_jump:
	la x6, _direct_jump
	jalr x0, x6, 0

_direct_jump:
	jal x0, _end

_direct_call_tgt:
	ret

_indirect_call_tgt:
	ret

_end:
	ebreak

