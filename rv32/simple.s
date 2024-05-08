.section .text
.global _start
_start:

.rept 32
	addi x0, x0, 0
	addi x0, x0, 1
	addi x0, x0, 2
	addi x0, x0, 3

	addi x0, x0, 4
	addi x0, x0, 5
	addi x0, x0, 6
	addi x0, x0, 7

	addi x0, x0, 8
	addi x0, x0, 9
	addi x0, x0, 10
	addi x0, x0, 11

	addi x0, x0, 12
	addi x0, x0, 13
	addi x0, x0, 14
	addi x0, x0, 15
.endr


