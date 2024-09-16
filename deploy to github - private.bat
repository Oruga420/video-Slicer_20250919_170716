@echo off
setlocal enabledelayedexpansion

:: Ensure the script doesn't close on errors
if not defined in_subprocess (cmd /k set in_subprocess=y ^& %0 %*) & exit )

echo Starting GitHub private repository creation script...

:: Check for Git
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: Git is not installed or not in the system PATH.
    echo Please install Git and try again.
    goto :error
)

:: Check for cURL
where curl >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: cURL is not installed or not in the system PATH.
    echo Please install cURL and try again.
    goto :error
)

:: Get GitHub credentials
:get_credentials
set /p "github_username=Enter your GitHub username: "
set /p "github_token=Enter your GitHub personal access token: "

if "%github_username%"=="" (
    echo Error: GitHub username cannot be empty.
    goto :get_credentials
)
if "%github_token%"=="" (
    echo Error: GitHub token cannot be empty.
    goto :get_credentials
)

:: Validate token
echo Validating GitHub token...
curl -s -H "Authorization: token %github_token%" https://api.github.com/user > nul
if %errorlevel% neq 0 (
    echo Error: Invalid GitHub token or authentication failed.
    goto :get_credentials
)

:: Get repository name
for %%I in (.) do set "repo_name=%%~nxI"
set "timestamp=%date:~-4,4%%date:~-10,2%%date:~-7,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "timestamp=%timestamp: =0%"
set "unique_repo_name=%repo_name%_%timestamp%"
set "url_repo_name=%unique_repo_name: =-%"
echo Repository name: %url_repo_name%

:: Initialize Git repository
git init
if %errorlevel% neq 0 (
    echo Error: Failed to initialize Git repository.
    goto :error
)

:: Add all files
git add .
if %errorlevel% neq 0 (
    echo Error: Failed to add files to Git repository.
    goto :error
)

:: Commit files
git commit -m "Initial commit"
if %errorlevel% neq 0 (
    echo Error: Failed to commit files.
    goto :error
)

:: Create GitHub repository
echo Creating private GitHub repository...
set "api_url=https://api.github.com/user/repos"
set "json_data={\"name\":\"%url_repo_name%\",\"private\":true}"

curl -s -H "Authorization: token %github_token%" ^
     -H "Content-Type: application/json" ^
     -X POST ^
     -d "%json_data%" ^
     "%api_url%" > repo_creation_response.json

if %errorlevel% neq 0 (
    echo Error: Failed to create GitHub repository.
    type repo_creation_response.json
    goto :error
)

:: Check if repository was created successfully
findstr /C:"\"name\": \"%url_repo_name%\"" repo_creation_response.json > nul
if %errorlevel% neq 0 (
    echo Error: Repository creation failed or returned unexpected response.
    type repo_creation_response.json
    goto :error
)

echo Private repository created successfully.

:: Check if remote origin exists and remove it
git remote -v | findstr "origin" > nul
if %errorlevel% equ 0 (
    echo A remote origin already exists. Removing it...
    git remote remove origin
    if !errorlevel! neq 0 (
        echo Error: Failed to remove existing remote.
        goto :error
    )
    echo Existing remote removed successfully.
)

:: Construct and display the remote URL
set "remote_url=https://github.com/%github_username%/%url_repo_name%.git"
echo.
echo Constructed remote URL: %remote_url%
echo.

:: Add remote
echo Adding new remote origin...
git remote add origin "%remote_url%"
if %errorlevel% neq 0 (
    echo Error: Failed to add remote origin.
    echo Current remotes:
    git remote -v
    goto :error
)

:: Verify remote was added correctly
echo Verifying remote...
for /f "tokens=2" %%a in ('git remote -v ^| findstr "(fetch)"') do set "actual_url=%%a"
echo Actual remote URL: !actual_url!

if not "!actual_url!"=="%remote_url%" (
    echo Error: Remote URL mismatch.
    echo Expected: %remote_url%
    echo Actual: !actual_url!
    goto :error
)

echo Remote origin added and verified successfully.

:: Get current branch name
for /f "tokens=2" %%i in ('git branch --show-current') do set "current_branch=%%i"
if "%current_branch%"=="" set "current_branch=master"

:: Commit any pending changes
git add .
git commit -m "Update before push" || echo No changes to commit.

:: Push to GitHub
echo Pushing to GitHub...
git push -u origin %current_branch%
if %errorlevel% neq 0 (
    echo Error: Failed to push to GitHub.
    echo Checking remote URL:
    git remote -v
    echo Checking branch name:
    git branch
    echo Checking git status:
    git status
    goto :error
)

echo Success! Private repository created and files pushed.
echo You can find your new private repository at: https://github.com/%github_username%/%url_repo_name%
goto :end

:error
echo An error occurred. Please check the output above for details.
pause
exit /b 1

:end
echo Script completed successfully.
pause