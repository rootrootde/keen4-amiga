#include "ck_amiga_test.h"

#include "ck_def.h"
#include "id_ca.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

bool CK_SaveGame(FILE *file);
bool CK_LoadGame(FILE *file, bool fromMenu);

bool CK_AmigaSaveLoadRoundtrip(const char *path, char *reason, size_t reasonSize)
{
	CK_GameState savedState = ck_gameState;
	CK_object savedObjects[CK_MAX_OBJECTS];
	unsigned count = 0;
	size_t mapBytes = (size_t)CA_GetMapWidth() * CA_GetMapHeight() * sizeof(uint16_t);
	uint8_t *maps = NULL;
	FILE *file = NULL;
	bool ok = false;
	if (!mapBytes || mapBytes > 65535)
	{
		snprintf(reason, reasonSize, "invalid map size");
		return false;
	}
	maps = malloc(mapBytes * 3);
	if (!maps)
	{
		snprintf(reason, reasonSize, "map snapshot allocation failed");
		return false;
	}
	for (int plane = 0; plane < 3; ++plane)
		memcpy(maps + plane * mapBytes, CA_TilePtrAtPos(0, 0, plane), mapBytes);
	for (CK_object *object = ck_keenObj; object; object = object->next)
	{
		if (count == CK_MAX_OBJECTS)
		{
			snprintf(reason, reasonSize, "object list exceeds limit");
			goto done;
		}
		savedObjects[count++] = *object;
	}
	if (count < 2)
	{
		snprintf(reason, reasonSize, "object list incomplete");
		goto done;
	}
	file = fopen(path, "wb");
	if (!file || !CK_SaveGame(file) || ferror(file))
	{
		snprintf(reason, reasonSize, "save failed");
		goto done;
	}
	if (fclose(file))
	{
		file = NULL;
		snprintf(reason, reasonSize, "save close failed");
		goto done;
	}
	file = NULL;
	ck_gameState.keenScore ^= 1;
	*CA_TilePtrAtPos(0, 0, 0) ^= 1;
	ck_keenObj->posX ^= 1;
	file = fopen(path, "rb");
	if (!file || !CK_LoadGame(file, false) || ferror(file))
	{
		snprintf(reason, reasonSize, "load failed");
		goto done;
	}
	if (fclose(file))
	{
		file = NULL;
		snprintf(reason, reasonSize, "load close failed");
		goto done;
	}
	file = NULL;
#define CHECK_STATE(field) do { if (ck_gameState.field != savedState.field) { \
		snprintf(reason, reasonSize, "state " #field " differs"); goto done; } } while (0)
	CHECK_STATE(mapPosX); CHECK_STATE(mapPosY); CHECK_STATE(keenScore);
	CHECK_STATE(nextKeenAt); CHECK_STATE(numShots); CHECK_STATE(numCentilife);
	CHECK_STATE(ep.ck4.wetsuit); CHECK_STATE(ep.ck4.membersRescued);
	CHECK_STATE(currentLevel); CHECK_STATE(numLives); CHECK_STATE(difficulty);
	if (memcmp(ck_gameState.levelsDone, savedState.levelsDone, sizeof(savedState.levelsDone)) ||
	    memcmp(ck_gameState.keyGems, savedState.keyGems, sizeof(savedState.keyGems)))
	{
		snprintf(reason, reasonSize, "state arrays differ");
		goto done;
	}
#undef CHECK_STATE
	for (int plane = 0; plane < 3; ++plane)
		if (memcmp(maps + plane * mapBytes, CA_TilePtrAtPos(0, 0, plane), mapBytes))
		{
			snprintf(reason, reasonSize, "map plane %d differs", plane);
			goto done;
		}
	CK_object *object = ck_keenObj;
	for (unsigned index = 0; index < count; ++index)
	{
		if (!object)
		{
			snprintf(reason, reasonSize, "object list shortened");
			goto done;
		}
		const CK_object *saved = &savedObjects[index];
#define CHECK_OBJECT(field) do { if (object->field != saved->field) { \
		snprintf(reason, reasonSize, "object %u " #field " differs", index); goto done; } } while (0)
		CHECK_OBJECT(type); CHECK_OBJECT(active); CHECK_OBJECT(clipped);
		CHECK_OBJECT(timeUntillThink); CHECK_OBJECT(posX); CHECK_OBJECT(posY);
		CHECK_OBJECT(xDirection); CHECK_OBJECT(yDirection);
		CHECK_OBJECT(deltaPosX); CHECK_OBJECT(deltaPosY);
		CHECK_OBJECT(velX); CHECK_OBJECT(velY); CHECK_OBJECT(actionTimer);
		CHECK_OBJECT(currentAction); CHECK_OBJECT(gfxChunk); CHECK_OBJECT(zLayer);
		CHECK_OBJECT(topTI); CHECK_OBJECT(rightTI); CHECK_OBJECT(bottomTI); CHECK_OBJECT(leftTI);
		if (memcmp(&object->clipRects, &saved->clipRects, sizeof(saved->clipRects)))
		{
			snprintf(reason, reasonSize, "object %u clip differs", index);
			goto done;
		}
		// Draw pointers, visibility and scorebox values are rebuilt by CK_LoadGame.
		if (index != 1)
		{
			CHECK_OBJECT(user1);
			if (object->type != CT4_Platform)
				CHECK_OBJECT(user2);
			if (object->type != CT4_Platform && object->type != CT_CLASS(StunnedCreature))
				CHECK_OBJECT(user3);
			CHECK_OBJECT(user4);
		}
		object = object->next;
#undef CHECK_OBJECT
	}
	if (object)
	{
		snprintf(reason, reasonSize, "object list length differs");
		goto done;
	}
	ok = true;
	snprintf(reason, reasonSize, "pass");
done:
	if (file && fclose(file) && ok)
	{
		ok = false;
		snprintf(reason, reasonSize, "file close failed");
	}
	free(maps);
	return ok;
}
