#ifndef CK_AMIGA_TEST_H
#define CK_AMIGA_TEST_H

#include <stdbool.h>
#include <stddef.h>

bool CK_AmigaSaveLoadRoundtrip(const char *path, char *reason, size_t reasonSize);

#endif
