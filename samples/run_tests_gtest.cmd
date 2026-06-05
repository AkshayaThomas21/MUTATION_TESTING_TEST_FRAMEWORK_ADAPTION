:: ==========================================================================
:: Script Name   : run_tests_gtest.cmd
:: Description   : 
::   This script builds the project using CMake and runs unit tests.
::   It uses TEST_TARGET to select the required test executable.
::
:: Workflow:
::   1. Validates TEST_TARGET input
::   2. Configures and builds project using CMake
::   3. Builds specific test target
::   4. Executes test binary
::   5. Returns PASS / FAIL based on exit code
::
:: Input:
::   TEST_TARGET (Environment Variable)
::   Example: UT_AppDcmHndlr.c or AppDcmHndlr.c
::
:: Output:
::   Exit Code:
::     0 → Tests Passed (PASS)
::     1 → Tests Failed (FAIL)
::     2 → Build/Error issue
::
:: Note:
::   - Designed for mutation testing pipeline
::   - Can be adapted for other test frameworks
::   - Requires CMake + MinGW setup
::
:: ==========================================================================

@echo off
setlocal EnableDelayedExpansion

:: Check if TEST_TARGET is provided 
if "%TEST_TARGET%"=="" (
    echo [ERROR] Environment variable TEST_TARGET not set!
    exit /b 2
)

:: Extract base name from TEST_TARGET (e.g. UT_Foo.c → UT_Foo)
set FILE_BASE=%TEST_TARGET:.c=%

:: Avoid double UT_ prefix
echo %FILE_BASE% | findstr /B "UT_" >nul
IF %ERRORLEVEL% EQU 0 (
    set TEST_TARGET=%FILE_BASE%
) ELSE (
    set TEST_TARGET=UT_%FILE_BASE%
)

set EXECUTABLE=host\%TEST_TARGET%.exe

:: ---------------------------------------------------------------------
:: COMPILER CONFIG
:: ---------------------------------------------------------------------

set C_COMPILER=C:/toolbase/mingw/comp_6.3.0_w64_1f/bin/gcc.exe
set CXX_COMPILER=C:/toolbase/mingw/comp_6.3.0_w64_1f/bin/g++.exe

:: ---------------------------------------------------------------------
:: PROJECT & TEST BUILD
:: ---------------------------------------------------------------------

echo [INFO] Configuring CMake...
cmake -S . -B build -G "MinGW Makefiles" ^
    -D CMAKE_C_COMPILER=%C_COMPILER% ^
    -D CMAKE_CXX_COMPILER=%CXX_COMPILER%
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] CMake configuration failed!
    exit /b 2
)

echo [INFO] Building full project...
cmake --build build
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Build failed!
    exit /b 2
)

echo [INFO] Building test target: %TEST_TARGET%
cmake --build build --target %TEST_TARGET%
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to build test target: %TEST_TARGET%
    exit /b 2
)

:: ---------------------------------------------------------------------
:: TEST EXECUTION
:: ---------------------------------------------------------------------

echo [INFO] Running test binary: build\%EXECUTABLE%
if exist build\%EXECUTABLE% (
    build\%EXECUTABLE%
    IF !ERRORLEVEL! EQU 0 (
        echo [PASS] Tests passed.
        exit /b 0
    ) ELSE (
        echo [FAIL] Some tests failed.
        exit /b 1
    )
) ELSE (
    echo [ERROR] Executable not found: build\%EXECUTABLE%
    exit /b 2
)

endlocal
