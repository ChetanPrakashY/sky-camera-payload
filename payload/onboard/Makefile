CC ?= gcc
CFLAGS ?= -std=c11 -O2 -Wall -Wextra -Werror -D_DEFAULT_SOURCE

procframe: procframe.c
	$(CC) $(CFLAGS) $< -o $@ -lm

# same program with address and undefined-behaviour checks, for testing
procframe-check: procframe.c
	$(CC) -std=c11 -O1 -g -Wall -Wextra -Werror -D_DEFAULT_SOURCE -fsanitize=address,undefined $< -o $@ -lm

clean:
	rm -f procframe procframe-check
.PHONY: clean
