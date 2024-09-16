@echo off
setlocal enabledelayedexpansion

echo Starting GitHub repository update script...

:: Enable logging
set "log_file=%TEMP%\github_update_log.txt"
echo Starting script execution at %date% %time% > "%log_file%"

:: Check for Git
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: Git is not installed or not in the system PATH.
    echo Please install Git and try again.
    echo Git not found >> "%log_file%"
    goto :error
)
echo Git found >> "%log_file%"

:: Check for cURL
where curl >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: cURL is not installed or not in the system PATH.
    echo Please install cURL and try again.
    echo cURL not found >> "%log_file%"
    goto :error
)
echo cURL found >> "%log_file%"

:: Get GitHub username
set /p "github_username=Enter your GitHub username: "
echo GitHub username: %github_username% >> "%log_file%"

:: Get repository name
set /p "repo_name=Enter the name of the repository you want to update: "
echo Repository name entered: %repo_name% >> "%log_file%"

:: Get GitHub token
set /p "github_token=Enter your GitHub personal access token: "
echo GitHub token received (not logged for security reasons) >> "%log_file%"

:: Use GitHub API to verify the repository exists
echo Verifying repository on GitHub...
echo Verifying repository on GitHub... >> "%log_file%"
set "api_url=https://api.github.com/repos/%github_username%/%repo_name%"
curl -s -H "Authorization: token %github_token%" "%api_url%" > api_response.json

:: Check for specific error messages in the API response
findstr /C:"Not Found" api_response.json > nul
if %errorlevel% equ 0 (
    echo Error: Repository not found.
    echo Repository not found >> "%log_file%"
    goto :error
)

findstr /C:"Bad credentials" api_response.json > nul
if %errorlevel% equ 0 (
    echo Error: Invalid GitHub token.
    echo Invalid GitHub token >> "%log_file%"
    goto :error
)

echo Repository verified on GitHub >> "%log_file%"

:: Create a temporary directory for the operation
set "temp_dir=%TEMP%\github_update_%random%"
mkdir "%temp_dir%"
echo Temporary directory created: %temp_dir% >> "%log_file%"

:: Clone the repository to the temporary directory
echo Cloning repository to temporary directory...
git clone "https://github.com/%github_username%/%repo_name%.git" "%temp_dir%"
if %errorlevel% neq 0 (
    echo Error: Failed to clone the repository.
    echo Failed to clone repository >> "%log_file%"
    goto :cleanup
)
echo Repository cloned successfully >> "%log_file%"

:: Copy all files from current directory to the temporary directory
echo Copying files from current directory to temporary repository...
xcopy /E /Y "%CD%" "%temp_dir%"
if %errorlevel% neq 0 (
    echo Error: Failed to copy files.
    echo Failed to copy files >> "%log_file%"
    goto :cleanup
)
echo Files copied successfully >> "%log_file%"

:: Change to the temporary directory
cd /d "%temp_dir%"
echo Changed to temporary directory: %CD% >> "%log_file%"

:: Display the files that will be updated
echo Files to be updated:
dir /B
echo Files to be updated: >> "%log_file%"
dir /B >> "%log_file%"

:: Prompt user to confirm update
set /p "confirm_update=Do you want to update these files on GitHub? (Y/N): "
echo Update confirmation: %confirm_update% >> "%log_file%"
if /i "%confirm_update%" neq "Y" goto :cleanup

:: Stage all changes
echo Staging all changes...
git add .
if %errorlevel% neq 0 (
    echo Error: Failed to stage changes.
    echo Failed to stage changes >> "%log_file%"
    goto :cleanup
)
echo Staging successful >> "%log_file%"

:: Commit changes
set /p "commit_message=Enter a commit message: "
if "%commit_message%"=="" set "commit_message=Update files"
echo Commit message: %commit_message% >> "%log_file%"

echo Committing changes...
git commit -m "%commit_message%"
if %errorlevel% neq 0 (
    echo Error: Failed to commit changes.
    echo Failed to commit changes >> "%log_file%"
    goto :cleanup
)
echo Commit successful >> "%log_file%"

:: Push changes
echo Pushing changes to GitHub...
git push
if %errorlevel% neq 0 (
    echo Error: Failed to push changes to GitHub.
    echo Failed to push changes >> "%log_file%"
    goto :cleanup
)
echo Push successful >> "%log_file%"

echo Success! Changes have been pushed to GitHub.
echo Script completed successfully >> "%log_file%"
goto :cleanup

:error
echo An error occurred. Please check the output above for details.
echo Error occurred. See log file for details: %log_file% >> "%log_file%"
echo Log file location: %log_file%
pause
exit /b 1

:cleanup
:: Clean up temporary directory
cd /d "%~dp0"
rmdir /S /Q "%temp_dir%"
echo Temporary directory cleaned up >> "%log_file%"

echo Script completed at %date% %time% >> "%log_file%"
echo Log file location: %log_file%
del api_response.json
pause