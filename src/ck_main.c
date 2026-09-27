/*
Omnispeak: A Commander Keen Reimplementation
Copyright (C) 2012 David Gow <david@ingeniumdigital.com>

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
 */

#include "id_ca.h"
#include "id_fs.h"
#include "id_in.h"
#include "id_mm.h"
#include "id_rf.h"
#include "id_us.h"
#include "id_vl.h"
#include "ck_act.h"
#include "ck_cross.h"
#include "ck_def.h"
#include "ck_game.h"
#include "ck_play.h"
#ifdef KEEN_AMIGA_RTG
#include "ck_amiga_test.h"
#include <exec/memory.h>
#include <proto/exec.h>
#endif
#ifdef WITH_KEEN4
#include "ck4_ep.h"
#endif
#ifdef WITH_KEEN5
#include "ck5_ep.h"
#endif
#ifdef WITH_KEEN6
#include "ck6_ep.h"
#endif

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef KEEN_AMIGA_RTG
#include <ctype.h>
#endif

#ifdef KEEN_AMIGA_RTG
static char amigaRunId[65];
static char amigaBuildId[65];
static bool amigaRunActive;
static bool amigaReplayRequested;
static bool amigaReplayFinished;
static uint32_t amigaDemoStartMs;
static uint32_t amigaDemoElapsedMs;
static uint32_t amigaDemoFirstTick;
static uint32_t amigaDemoLastTick;
static uint32_t amigaDemoFrames;
static unsigned amigaStressCycles;

void SD_SDL_GetAudioMetrics(bool *opened, uint32_t *callbacks,
	uint32_t *nonzeroSamples, uint32_t *entered, uint32_t *completed,
	uint32_t *invalid, uint32_t *sampleRate, uint32_t *channels,
	uint32_t *bufferSamples);

static bool CK_AmigaRunToken(const char *value)
{
	if (!value || !*value || strlen(value) >= sizeof(amigaRunId))
		return false;
	for (; *value; ++value)
		if (!isalnum((unsigned char)*value) && *value != '-' && *value != '_')
			return false;
	return true;
}

static bool CK_AmigaRunRecord(const char *suffix, const char *body)
{
	char path[96], temporary[100];
	snprintf(path, sizeof(path), "RESULT:%s.%s", amigaRunId, suffix);
	snprintf(temporary, sizeof(temporary), "%s.tmp", path);
	FILE *file = fopen(temporary, "wb");
	if (!file)
		return false;
	int written = fprintf(file, "run_id=%s\nbuild_id=%s\n%s", amigaRunId, amigaBuildId, body);
	int closed = fclose(file);
	if (written < 0 || closed || rename(temporary, path))
		return false;
	return true;
}

static bool CK_AmigaRunStart(int argc, char **argv)
{
	const char *runId = NULL, *buildId = NULL;
	for (int i = 1; i < argc; ++i)
	{
		if (!CK_Cross_strcasecmp(argv[i], "/RUNID") && i + 1 < argc)
			runId = argv[++i];
		else if (!CK_Cross_strcasecmp(argv[i], "/BUILDID") && i + 1 < argc)
			buildId = argv[++i];
	}
	if (!runId && !buildId)
		return true;
	if (!CK_AmigaRunToken(runId) || !CK_AmigaRunToken(buildId))
		return false;
	strcpy(amigaRunId, runId);
	strcpy(amigaBuildId, buildId);
	amigaRunActive = true;
	return CK_AmigaRunRecord("start", "state=started\n");
}

static bool CK_AmigaStressCount(int argc, char **argv)
{
	for (int i = 1; i < argc; ++i)
		if (!CK_Cross_strcasecmp(argv[i], "/STRESS"))
		{
			char *end;
			long count;
			if (++i == argc)
				return false;
			count = strtol(argv[i], &end, 10);
			if (*end || count < 2 || count > 100 || amigaStressCycles)
				return false;
			amigaStressCycles = (unsigned)count;
		}
	return true;
}

void CK_AmigaRunProgress(const char *event)
{
	if (!amigaRunActive)
		return;
	char path[96];
	snprintf(path, sizeof(path), "RESULT:%s.progress", amigaRunId);
	FILE *file = fopen(path, "ab");
	if (file)
	{
		fprintf(file, "run_id=%s build_id=%s event=%s\n",
		        amigaRunId, amigaBuildId, event);
		fclose(file);
	}
}

void CK_AmigaRunDemoTick(uint32_t tick)
{
	if (!amigaDemoFrames)
		amigaDemoFirstTick = tick;
	amigaDemoLastTick = tick;
	++amigaDemoFrames;
}

bool CK_AmigaRunFinish(bool normal)
{
	if (!amigaRunActive)
		return true;
	bool pass = normal && (!amigaReplayRequested || amigaReplayFinished);
	bool audioOpened;
	uint32_t callbacks, nonzeroSamples;
	uint32_t callbackEntered, callbackCompleted, callbackInvalid;
	uint32_t sampleRate, channels, bufferSamples;
	SD_SDL_GetAudioMetrics(&audioOpened, &callbacks, &nonzeroSamples,
	                       &callbackEntered, &callbackCompleted, &callbackInvalid,
	                       &sampleRate, &channels, &bufferSamples);
	char body[512];
	snprintf(body, sizeof(body),
	         "state=finished\nresult=%s\naudio_opened=%u\naudio_callbacks=%lu\n"
	         "audio_nonzero_samples=%lu\naudio_callback_entered=%lu\n"
	         "audio_callback_completed=%lu\naudio_invalid_callbacks=%lu\n"
	         "audio_sample_rate=%lu\naudio_channels=%lu\naudio_buffer_samples=%lu\n"
	         "audio_audible=unverified\n"
	         "demo_elapsed_ms=%lu\ndemo_elapsed_ticks=%lu\ndemo_frames=%lu\n",
	         pass ? "pass" : "fail", audioOpened ? 1u : 0u,
	         (unsigned long)callbacks, (unsigned long)nonzeroSamples,
	         (unsigned long)callbackEntered, (unsigned long)callbackCompleted,
	         (unsigned long)callbackInvalid,
	         (unsigned long)sampleRate, (unsigned long)channels,
	         (unsigned long)bufferSamples,
	         (unsigned long)amigaDemoElapsedMs,
	         (unsigned long)(amigaDemoLastTick - amigaDemoFirstTick),
	         (unsigned long)amigaDemoFrames);
	CK_AmigaRunProgress(pass ? "finished" : "failed");
	return CK_AmigaRunRecord("result", body) && pass;
}
#endif

/*
 * The 'episode' we're playing.
 */
CK_EpisodeDef *ck_currentEpisode;

// Are we running the "in-store demo", which quits after a few levels.
bool ck_storeDemo = false;

/*
 * Measure the containing box size of a string that spans multiple lines
 */
void CK_MeasureMultiline(const char *str, uint16_t *w, uint16_t *h)
{
	char c;
	uint16_t x, y;
	char buf[80] = {0};
	char *p;

	*h = *w = (uint16_t)0;
	p = buf; /* must be a local buffer */

	while ((c = *str++) != 0)
	{
		*p++ = c;

		if (c == '\n' || *str == 0)
		{
			VH_MeasurePropString(buf, &x, &y, US_GetPrintFont());

			*h += y;
			if (*w < x)
				*w = x;

			p = (char *)buf;
			// Shouldn't buf be cleared so that a newline is not read over by
			// VH_MeasurePropString?
		}
	}
}

/*
 * Shutdown all of the 'ID Engine' components
 */
void CK_ShutdownID(void)
{
	//TODO: Some managers don't have shutdown implemented yet
	VL_DestroySurface(ck_backupSurface);
	VL_DestroySurface(ck_statusSurface);
	US_Shutdown();
	SD_Shutdown();
	//IN
	RF_Shutdown();
	//VH
	VL_Shutdown();
	CA_Shutdown();

	CFG_Shutdown();
	MM_Shutdown();

#ifdef WITH_SDL
	SDL_Quit();
#endif
}

/*
 * Start the game!
 */

void CK_InitGame()
{
	// On Windows, we want to be DPI-aware
#if defined(WITH_SDL) && defined(_WIN32)
#if SDL_VERSION_ATLEAST(2,24,0) && !SDL_VERSION_ATLEAST(3,0,0)
	SDL_SetHint(SDL_HINT_WINDOWS_DPI_SCALING, "1");
#endif
#endif

	// Set the default high scores once we've loaded the episode.
	CK_SetDefaultHighScores();

	// Load the core datafiles
	CA_Startup();
	CA_InitLumps();
	// Setup saved games handling
	US_Setup();

	// Set a few Menu Callbacks
	// TODO: Finish this!
	US_SetMenuFunctionPointers(&CK_LoadGame, &CK_SaveGame, &CK_ExitMenu);
	// Set ID engine Callbacks
	ca_beginCacheBox = CK_BeginCacheBox;
	ca_updateCacheBox = CK_UpdateCacheBox;
	ca_finishCacheBox = CK_FinishCacheBox;

	// Mark some chunks we'll need.
	CA_ClearMarks();
	CA_MarkGrChunk(CK_CHUNKNUM(FON_MAINFONT));
	CA_MarkGrChunk(ca_gfxInfoE.offTiles8);
	CA_MarkGrChunk(ca_gfxInfoE.offTiles8m);
	CA_MarkGrChunk(CK_CHUNKNUM(MPIC_STATUSLEFT));
	CA_MarkGrChunk(CK_CHUNKNUM(MPIC_STATUSRIGHT));
	CA_MarkGrChunk(CK_CHUNKNUM(PIC_TITLESCREEN)); // Moved from CA_Startup
	CA_CacheMarks(0);

	// Lock them chunks in memory.
	CA_LockGrChunk(CK_CHUNKNUM(FON_MAINFONT));
	CA_LockGrChunk(ca_gfxInfoE.offTiles8);
	CA_LockGrChunk(ca_gfxInfoE.offTiles8m);
	CA_LockGrChunk(CK_CHUNKNUM(MPIC_STATUSLEFT));
	CA_LockGrChunk(CK_CHUNKNUM(MPIC_STATUSRIGHT));

	// Setup the screen
	VL_Startup();
	// TODO: Palette initialization should be done in the terminator code
	VL_SetDefaultPalette();

	// Setup input
	IN_Startup();

	// Setup audio
	SD_Startup();

	US_Startup();

	// Wolf loads fonts here, but we do it in CA_Startup()?

	RF_Startup();

	VL_ColorBorder(3);
	VL_ClearScreen(0);
	VL_Present();

	// Create a surface for the dropdown menu
	ck_statusSurface = VL_CreateSurface(RF_BUFFER_WIDTH_PIXELS, STATUS_H + 16 + 16);
	ck_backupSurface = VL_CreateSurface(RF_BUFFER_WIDTH_PIXELS, RF_BUFFER_HEIGHT_PIXELS);
}

/*
 * The Demo Loop
 * Keen (and indeed Wolf3D) have this function as the core of the game.
 * It is, in essence, a loop which runs the title/demos, and calls into the
 * main menu and game loops when they are required.
 */

extern CK_Difficulty ck_startingDifficulty;

void CK_DemoLoop()
{
	/*
	 * Commander Keen could be 'launched' from the map editor TED to test a map.
	 * This was implemented by having TED launch keen with the /TEDLEVEL xx
	 * parameter, where xx is the level number.
	 */

	if (us_tedLevel)
	{
		static const char *difficultyParms[] = {"easy", "normal", "hard", ""};
		CK_NewGame();
		CA_LoadAllSounds();
		ck_gameState.currentLevel = us_tedLevelNumber;
		ck_startingDifficulty = D_Normal;

		for (int i = 1; i < us_argc; ++i)
		{
			int difficulty = US_CheckParm(us_argv[i], difficultyParms);
			if (difficulty == -1)
				continue;

			ck_startingDifficulty = (CK_Difficulty)((int)D_Easy + difficulty);
			break;
		}

		CK_GameLoop();
		Quit(0); // run_ted
	}

	/*
	 * Handle "easy" "normal" and "hard" parameters here
	 */

	// Given we're not coming from TED, run through the demos.

	int demoNumber = 0;
	ck_gameState.levelState = LS_Playing;

	while (true)
	{
		switch (demoNumber++)
		{
		case 0: // Terminator scroller and Title Screen
			// If no pixel panning capability
			// Then the terminator screen isn't shown
			if (vl_noPan)
				CK_ShowTitleScreen();
			else
				CK_DrawTerminator();
#if 1					     //DEMO_LOOP_ENABLED
			break;
		case 1:
			CK_PlayDemo(0);
			break;
		case 2:
			// Star Wars story text
			CK_DrawStarWars();
			break;
		case 3:
			CK_PlayDemo(1);
			break;
		case 4:
			CK_DoHighScores(); // High Scores
			// CK_PlayDemo(4);
			break;
		case 5:
			CK_PlayDemo(2);
			break;
		case 6:
			CK_PlayDemo(3);
#else
			CK_HandleDemoKeys();
#endif
			demoNumber = 0;
			break;
		}

		// Game Loop
		while (1)
		{
			if (ck_gameState.levelState == LS_ResetGame || ck_gameState.levelState == LS_LoadedGame)
			{
				CK_GameLoop();
				CK_DoHighScores();
				if (ck_gameState.levelState == LS_ResetGame || ck_gameState.levelState == LS_LoadedGame)
					continue;

				CK_ShowTitleScreen();

				if (ck_gameState.levelState == LS_ResetGame || ck_gameState.levelState == LS_LoadedGame)
					continue;
			}
			else
			{
				break;
			}
		}
	}

	Quit("Demo loop exited!?");
}

/* Basically a set of hacks: By commenting out the relevant "define" line,
 * this code piece can be used to build a validator that checks that the
 * contents of an ACTION.EXT file match the ones from an original
 * (but unpacked) DOS executable, to find any missed difference.
 * Note that the validation of function pointers isn't precise, but it
 * is checked that different occurrences of the same function pointer in
 * a DOS EXE always map to the exact same function in the ACTION.EXT file.
 */

//#define CK_RUN_ACTION_VALIDATOR

#ifdef CK_RUN_ACTION_VALIDATOR

#ifndef CK_CROSS_IS_LITTLEENDIAN
#error "Error - Action validator is compatible with little-endian only!"
#endif

#include <stdio.h>
#include "id_str.h"

#define MAX_NUM_OF_FUNCTIONS 256


typedef enum CK_VAR_VarType
{
	VAR_Invalid,
	VAR_EOF,
	VAR_Bool,
	VAR_Int,
	VAR_String,
	VAR_IntArray,
	VAR_StringArray,
	VAR_Action,
	VAR_TOK_Include
} CK_VAR_VarType;

#ifdef CK_VAR_TYPECHECK
typedef struct CK_VAR_Variable
{
	CK_VAR_VarType type;
	void *value;
	size_t arrayLength;
} CK_VAR_Variable;
#else
#error Action validator requires typechecking to be enabled.
#endif

extern STR_Table *ck_varTable; // HACK

typedef struct
{
	uint32_t farPtr;
	void *nativePtr;
} CK_FuncPtrPair;

// Using an array for the sake of simplicity
static CK_FuncPtrPair ck_funcPtrPairsArray[MAX_NUM_OF_FUNCTIONS];
static int g_numOfFunctPtrPairs = 0;

static bool compareFunctionDOSPtrToNativePtr(uint32_t farPtr, void *nativePtr)
{
	if ((farPtr == 0) || (nativePtr == NULL))
		return ((farPtr == 0) && (nativePtr == NULL));

	int i;
	CK_FuncPtrPair *funcPtrPair = ck_funcPtrPairsArray;
	for (i = 0; i < g_numOfFunctPtrPairs; ++i, ++funcPtrPair)
		if (funcPtrPair->farPtr == farPtr)
			return (funcPtrPair->nativePtr == nativePtr);

	// First time we encounter this function, so add a mapping if there's the room
	if (i == MAX_NUM_OF_FUNCTIONS)
	{
		fprintf(stderr, "Function pointers pairs array is full: DOS pointer is %u\n", (unsigned int)farPtr);
		exit(1);
	}
	funcPtrPair->farPtr = farPtr;
	funcPtrPair->nativePtr = nativePtr;
	++g_numOfFunctPtrPairs;
	return true;
}

int main(int argc, char *argv[])
{
	if (argc != 4)
	{
		printf("Action validator - Usage:\n");
		printf("%s <UNPACKED.EXE> <ACTION.EXT> <EPISODENUM>\n", argv[0]);
		return 0;
	}

	switch (atoi(argv[3]))
	{
	case 4:
		ck_currentEpisode = &ck4_episode;
		break;
	case 5:
		ck_currentEpisode = &ck5_episode;
		break;
	case 6:
		ck_currentEpisode = &ck6v14e_episode;
		break;
	default:
		fprintf(stderr, "Invalid episode selected - only 4 or 5 is valid!\n");
		return 1;
	}

	FILE *exeFp = fopen(argv[1], "rb");
	if (exeFp == NULL)
	{
		fprintf(stderr, "Couldn't open DOS EXE file! %s:\n", argv[1]);
		return 1;
	}
	fseek(exeFp, 0L, SEEK_END);
	long int fSize = ftell(exeFp);
	fseek(exeFp, 0L, SEEK_SET);

	char *fileBuffer = (char *)malloc(fSize);
	if (!fileBuffer)
	{
		fprintf(stderr, "Couldn't allocate memory for DOS EXE!\n");
		fclose(exeFp);
		return 1;
	}

	fread(fileBuffer, fSize, 1, exeFp);
	fclose(exeFp);

	// We need this here
	MM_Startup();
	FS_Startup();

	// Compile the actions
	CK_VAR_Startup();
	CK_ACT_SetupFunctions();
	CK_KeenSetupFunctions();
	CK_OBJ_SetupFunctions();
	CK_Map_SetupFunctions();
	CK_Misc_SetupFunctions();
	ck_currentEpisode->setupFunctions();
	CK_VAR_LoadVars(argv[2]);

	char *exeImage = fileBuffer + 16 * (*(uint16_t *)(fileBuffer + 8));
	char *dsegBuffer = exeImage + 16 * (*(uint16_t *)(exeImage + 1)); // HUGE HACK for fetching dseg

	// HACK
	extern STR_Table *ck_varTable;
	for (int i = 0, count = 0; i < ck_varTable->size; ++i)
	{
		if (ck_varTable->arr[i].str == NULL)
			continue;

		const char *name = ck_varTable->arr[i].str;
		CK_VAR_Variable *var = (CK_VAR_Variable *)(ck_varTable->arr[i].ptr);
		if (var->type != VAR_Action)
			continue;

		CK_action *act = (CK_action *)(var->value);

		char *dataToCompare = &dsegBuffer[act->compatDosPointer];
		if (*(int16_t *)dataToCompare != act->chunkLeft)
			printf("chunkLeft mismatch found for action no. %d: %s\n", count, name);
		if (*(int16_t *)(dataToCompare + 2) != act->chunkRight)
			printf("chunkRight mismatch found for action no. %d: %s\n", count, name);
		if (*(int16_t *)(dataToCompare + 4) != act->type)
			printf("type mismatch found for action no. %d: %s\n", count, name);
		if (*(int16_t *)(dataToCompare + 6) != act->protectAnimation)
			printf("protectAnimation mismatch found for action no. %d: %s\n", count, name);
		if (*(int16_t *)(dataToCompare + 8) != act->stickToGround)
			printf("stickToGround mismatch found for action no. %d: %s\n", count, name);
		if (*(int16_t *)(dataToCompare + 10) != act->timer)
			printf("timer mismatch found for action no. %d: %s\n", count, name);
		if (*(int16_t *)(dataToCompare + 12) != act->velX)
			printf("velX mismatch found for action no. %d: %s\n", count, name);
		if (*(int16_t *)(dataToCompare + 14) != act->velY)
			printf("velY mismatch found for action no. %d: %s\n", count, name);
		if (!compareFunctionDOSPtrToNativePtr(*(uint32_t *)(dataToCompare + 16), (void *)(act->think)))
			printf("think mismatch found (possibly) for action no. %d: %s\n", count, name);
		if (!compareFunctionDOSPtrToNativePtr(*(uint32_t *)(dataToCompare + 20), (void *)(act->collide)))
			printf("collide mismatch found (possibly) for action no. %d: %s\n", count, name);
		if (!compareFunctionDOSPtrToNativePtr(*(uint32_t *)(dataToCompare + 24), (void *)(act->draw)))
			printf("draw mismatch found (possibly) for action no. %d: %s\n", count, name);
		if (((act->next == NULL) && (*(uint16_t *)(dataToCompare + 28) != 0)) ||
			((act->next != NULL) && (*(uint16_t *)(dataToCompare + 28) != act->next->compatDosPointer)))
			printf("next mismatch found for action no. %d: %s\n", count, name);

		++count;
	}
	return 0;
}

#else // !CK_RUN_ACTION_VALIDATOR

CK_EpisodeDef *ck_episodes[] = {
#ifdef WITH_KEEN4
	&ck4_episode,
#endif
#ifdef WITH_KEEN5
	&ck5_episode,
#endif
#ifdef WITH_KEEN6
	&ck6_episode,
#endif
	0
};

extern bool ck6_creatureQuestionDone;

const char *ck_episodeFile = NULL;

int main(int argc, char *argv[])
{
#ifdef KEEN_AMIGA_RTG
	if (!CK_AmigaRunStart(argc, argv))
	{
		fprintf(stderr, "Invalid run identity or start record\n");
		return 2;
	}
	if (!CK_AmigaStressCount(argc, argv))
	{
		fprintf(stderr, "Invalid stress count\n");
		return 2;
	}
	CK_AmigaRunProgress("engine_start");
#endif
	// Send the cmd-line args to the User Manager.
	us_argc = argc;
	us_argv = (const char **)argv;

	// Check if we're running the store demo.
	if (US_ParmPresent("DEMO"))
		ck_storeDemo = true;

	// We need to start the filesystem code before we look
	// for any files.
	FS_Startup();

	// Can't do much without memory!
	MM_Startup();

	// Load the config file. We do this before parsing command-line args.
	CFG_Startup();

	ck_cross_logLevel = (CK_Log_Message_Class_T)CFG_GetConfigEnum("logLevel", ck_cross_logLevel_strings, CK_DEFAULT_LOG_LEVEL);

	// Compile the actions
	CK_ACT_SetupFunctions();
	CK_KeenSetupFunctions();
	CK_OBJ_SetupFunctions();
	CK_Map_SetupFunctions();
	CK_Misc_SetupFunctions();

	// Set up all of the episode functions.
#ifdef WITH_KEEN4
	CK4_SetupFunctions();
#endif
#ifdef WITH_KEEN5
	CK5_SetupFunctions();
#endif
#ifdef WITH_KEEN6
	CK6_SetupFunctions();
#endif

	CK_VAR_Startup();

	// Default to the first episode with all files present.
	// If no episodes are found, we default to the first DEMO_LOOP_ENABLED
	// epside (usually Keen 4) in order to show the file not found messages.
	ck_currentEpisode = ck_episodes[0];
	for (int i = 0; ck_episodes[i]; ++i)
	{
		if (ck_episodes[i]->isPresent())
		{
			ck_currentEpisode = ck_episodes[i];
			ck_episodeFile = ck_currentEpisode->episodeFile;
			break;
		}
	}

	// If we don't have an episode with all files present, look for _just_
	// an EPISODE.CKx file. This will often be the case for mods, which may
	// rename files.
	if (!ck_episodeFile)
	{
		for (int i = 0; ck_episodes[i]; ++i)
		{
			if (FS_IsOmniFilePresent(ck_episodes[i]->episodeFile))
			{
				ck_currentEpisode = ck_episodes[i];
				ck_episodeFile = ck_currentEpisode->episodeFile;
				break;
			}
		}
	}

	bool isFullScreen = CFG_GetConfigBool("fullscreen", false);
	bool isAspectCorrected = CFG_GetConfigBool("aspect", true);
	bool hasBorder = CFG_GetConfigBool("border", true);
	bool isIntegerScaled = CFG_GetConfigBool("integer", false);
	bool overrideCopyProtection = CFG_GetConfigBool("ck6_noCreatureQuestion", false);
	int swapInterval = CFG_GetConfigInt("swapInterval", 1);
#ifdef CK_ENABLE_PLAYLOOP_DUMPER
	const char *dumperFilename = NULL;
#endif

	for (int i = 1; i < argc; ++i)
	{
		if (!CK_Cross_strcasecmp(argv[i], "/EPISODE"))
		{
			// A bit of stuff from the usual demo loop
			if (argc >= i + 1)
			{
				if (FS_IsOmniFilePresent(argv[i + 1]))
					ck_episodeFile = argv[i + 1];
				else
#ifdef WITH_KEEN4
				if (!strcmp(argv[i + 1], "4"))
					ck_episodeFile = "EPISODE.CK4";
				else
#endif
#ifdef WITH_KEEN5
				if (!strcmp(argv[i + 1], "5"))
					ck_episodeFile = "EPISODE.CK5";
				else
#endif
#ifdef WITH_KEEN6
				if (!strcmp(argv[i + 1], "6"))
					ck_episodeFile = "EPISODE.CK6";
				// For compatibility, we accept version-specific arguments for 6,
				// as this used to matter. Now, as long as the data file are
				// correct, either work.
				else if (!strcmp(argv[i + 1], "6v14"))
					ck_episodeFile = "EPISODE.CK6";
				else if (!strcmp(argv[i + 1], "6v15"))
					ck_episodeFile = "EPISODE.CK6";
				else
#endif
					QuitF("Unsupported episode \"%s\"!", argv[i + 1]);
			}
		}
		else if (!CK_Cross_strcasecmp(argv[i], "/FULLSCREEN"))
		{
			isFullScreen = true;
		}
		else if (!CK_Cross_strcasecmp(argv[i], "/FILLED"))
		{
			isAspectCorrected = false;
		}
		else if (!CK_Cross_strcasecmp(argv[i], "/NOBORDER"))
		{
			hasBorder = false;
		}
		else if (!CK_Cross_strcasecmp(argv[i], "/INTEGER"))
		{
			isIntegerScaled = true;
		}
		else if (!CK_Cross_strcasecmp(argv[i], "/VSYNC"))
		{
			swapInterval = 1;
		}
		else if (!CK_Cross_strcasecmp(argv[i], "/NOVSYNC"))
		{
			swapInterval = 0;
		}
		else if (!CK_Cross_strcasecmp(argv[i], "/NOJOYS"))
		{
			in_disableJoysticks = true;
		}
		else if (!CK_Cross_strcasecmp(argv[i], "/NOCOPY"))
		{
			overrideCopyProtection = true;
		}
#ifdef CK_ENABLE_PLAYLOOP_DUMPER
		else if (!CK_Cross_strcasecmp(argv[i], "/DUMPFILE"))
		{
			if (i + 1 < argc)
				dumperFilename = argv[++i]; // Yes, we increment i twice
			else
				Quit("Missing dump file path");
		}
#endif
	}

	// Load the EPISODE.CKx file.
	if (!ck_episodeFile)
		Quit("No episode found! Make sure the game files are present, and run with /EPISODE <EPISODE.CKx>");
	CK_VAR_LoadVars(ck_episodeFile);

	// Determine the base episode number
	int episodeNumber = CK_INT(ck_episodeNumber, -1);
	if (episodeNumber == -1)
	{
		CK_Cross_LogMessage(CK_LOG_MSG_WARNING, "Episode doesn't declare a base episode number.\n");
		int fnamelen = strlen(ck_episodeFile);
		if (ck_episodeFile[fnamelen-4] == '.' && tolower(ck_episodeFile[fnamelen-3]) == 'c' && tolower(ck_episodeFile[fnamelen-2]) == 'k')
		{
			switch (ck_episodeFile[fnamelen-1])
			{
			case '4':
				episodeNumber = 4;
				CK_Cross_LogMessage(CK_LOG_MSG_WARNING, "Assuming episode 4 from filename %s\n", ck_episodeFile);
				break;
			case '5':
				episodeNumber = 5;
				CK_Cross_LogMessage(CK_LOG_MSG_WARNING, "Assuming episode 5 from filename %s\n", ck_episodeFile);
				break;
			case '6':
				episodeNumber = 6;
				CK_Cross_LogMessage(CK_LOG_MSG_WARNING, "Assuming episode 6 from filename %s\n", ck_episodeFile);
				break;
			default:
				QuitF("Episode %s doesn't provide an episode number, and one couldn't be guessed from the filename.", ck_episodeFile);
			}
		}
	}
	switch (episodeNumber)
	{
	case 4:
#ifdef WITH_KEEN4
		ck_currentEpisode = &ck4_episode;
#else
		Quit("This build of Omnispeak doesn't support Keen 4!");
#endif
		break;
	case 5:
#ifdef WITH_KEEN5
		ck_currentEpisode = &ck5_episode;
#else
		Quit("This build of Omnispeak doesn't support Keen 5!");
#endif
		break;
	case 6:
#ifdef WITH_KEEN6
		ck_currentEpisode = &ck6_episode;
#else
		Quit("This build of Omnispeak doesn't support Keen 6!");
#endif
		break;
	default:
		QuitF("No base episode specified in %s\n", ck_episodeFile);
	}

#ifdef CK_ENABLE_PLAYLOOP_DUMPER
	extern FILE *ck_dumperFile;
	if (dumperFilename != NULL)
	{
		ck_dumperFile = fopen(dumperFilename, "wb");
		if (ck_dumperFile == NULL)
		{
			Quit("Couldn't open dumper file for writing.");
		}
		printf("Writing to dump file %s\n", dumperFilename);
	}
#endif

	vl_swapInterval = swapInterval;
	VL_SetParams(isFullScreen, isAspectCorrected, hasBorder, isIntegerScaled);

	if (overrideCopyProtection)
		ck6_creatureQuestionDone = true;

	CK_InitGame();

	for (int i = 1; i < argc; ++i)
	{
		if (!CK_Cross_strcasecmp(argv[i], "/DEMOFILE"))
		{
			// A bit of stuff from the usual demo loop
			ck_gameState.levelState = LS_Playing;

			CK_PlayDemoFile(argv[i + 1]);
			Quit(0);
		}
		else if (!CK_Cross_strcasecmp(argv[i], "/PLAYDEMO"))
		{
			// A bit of stuff from the usual demo loop
			ck_gameState.levelState = LS_Playing;

			if (i + 1 >= argc || argv[i + 1][0] < '0' || argv[i + 1][0] > '4' || argv[i + 1][1])
				Quit("Invalid demo number");
#ifdef KEEN_AMIGA_RTG
			amigaReplayRequested = true;
			if (amigaStressCycles && (!amigaRunActive || !dumperFilename))
				Quit("Stress needs run identity and dump path");
			unsigned cycles = amigaStressCycles ? amigaStressCycles : 1;
			for (unsigned cycle = 1; cycle <= cycles; ++cycle)
			{
				bool opened;
				uint32_t callbacksBefore, nonzeroBefore, enteredBefore, completedBefore;
				uint32_t invalidBefore, sampleRate, channels, bufferSamples;
				uint32_t callbacksAfter, nonzeroAfter, enteredAfter, completedAfter, invalidAfter;
				char suffix[16], body[640], savePath[96], reason[96];
				if (cycle > 1)
				{
					char dumpPath[96];
					snprintf(dumpPath, sizeof(dumpPath), "RESULT:cycle%03u.dump", cycle);
					ck_dumperFile = fopen(dumpPath, "wb");
					if (!ck_dumperFile)
						Quit("Stress dump open failed");
				}
				amigaDemoFrames = amigaDemoFirstTick = amigaDemoLastTick = 0;
				SD_SDL_GetAudioMetrics(&opened, &callbacksBefore, &nonzeroBefore,
				                       &enteredBefore, &completedBefore, &invalidBefore,
				                       &sampleRate, &channels, &bufferSamples);
				ck_gameState.levelState = LS_Playing;
				amigaDemoStartMs = SDL_GetTicks();
				CK_AmigaRunProgress("demo_started");
				CK_PlayDemo(atoi(argv[i + 1]));
				amigaDemoElapsedMs = SDL_GetTicks() - amigaDemoStartMs;
				CK_AmigaRunProgress("demo_returned");
				if (amigaStressCycles)
				{
					int dumpError = ferror(ck_dumperFile);
					int closeError = fclose(ck_dumperFile);
					ck_dumperFile = NULL;
					if (dumpError || closeError)
						Quit("Stress dump close failed");
					snprintf(savePath, sizeof(savePath), "RESULT:%s.save-%03u", amigaRunId, cycle);
					if (!CK_AmigaSaveLoadRoundtrip(savePath, reason, sizeof(reason)))
						QuitF("Stress save/load: %s", reason);
					SD_SDL_GetAudioMetrics(&opened, &callbacksAfter, &nonzeroAfter,
					                       &enteredAfter, &completedAfter, &invalidAfter,
					                       &sampleRate, &channels, &bufferSamples);
					snprintf(suffix, sizeof(suffix), "cycle%03u", cycle);
					snprintf(body, sizeof(body),
					         "state=finished\nresult=pass\ncycle=%u\nframes=%lu\nticks=%lu\n"
					         "elapsed_ms=%lu\naudio_callbacks_delta=%lu\naudio_nonzero_delta=%lu\n"
					         "audio_entered_delta=%lu\naudio_completed_delta=%lu\n"
					         "audio_invalid_delta=%lu\nmm_used_memory=%d\nmm_used_blocks=%d\n"
					         "mm_purgable_blocks=%d\nvl_mem_used=%d\nvl_num_surfaces=%d\n"
					         "avail_mem=%lu\nsave_load=pass\n",
					         cycle, (unsigned long)amigaDemoFrames,
					         (unsigned long)(amigaDemoLastTick - amigaDemoFirstTick),
					         (unsigned long)amigaDemoElapsedMs,
					         (unsigned long)(callbacksAfter - callbacksBefore),
					         (unsigned long)(nonzeroAfter - nonzeroBefore),
					         (unsigned long)(enteredAfter - enteredBefore),
					         (unsigned long)(completedAfter - completedBefore),
					         (unsigned long)(invalidAfter - invalidBefore),
					         MM_UsedMemory(), MM_UsedBlocks(), MM_PurgableBlocks(),
					         VL_MemUsed(), VL_NumSurfaces(), (unsigned long)AvailMem(MEMF_ANY));
					if (!CK_AmigaRunRecord(suffix, body))
						Quit("Stress record failed");
				}
			}
			amigaReplayFinished = true;
#else
			CK_PlayDemo(atoi(argv[i + 1]));
#endif
			Quit(0);
		}
		else if (!CK_Cross_strcasecmp(argv[i], "/ASLEV"))
		{
			us_tedLevel = true;
			us_aslevFilename = argv[++i];

		}

	}

	if (us_noWait || us_tedLevel || CFG_GetConfigBool("debugActive", false))
		ck_debugActive = true;

	// Draw the ANSI "Press Key When Ready Screen" here
	CK_DemoLoop();
	CK_ShutdownID();
#ifdef CK_ENABLE_PLAYLOOP_DUMPER
	if (ck_dumperFile)
	{
		if (fclose(ck_dumperFile))
		{
#ifdef KEEN_AMIGA_RTG
			CK_AmigaRunFinish(false);
#endif
			return 1;
		}
		ck_dumperFile = NULL;
	}
#endif
#ifdef KEEN_AMIGA_RTG
	return CK_AmigaRunFinish(true) ? 0 : 1;
#endif
	return 0;
}

#endif // CK_RUN_ACTION_VALIDATOR
