@echo off
echo Building RAR processor Docker image...
docker build -t disk-management-rar-processor -f Dockerfile.rar_processor .

echo.
echo Starting RAR processor container...
docker run -d ^
    --name rar-processor ^
    -p 5001:5001 ^
    -v "%CD%\shared:/shared" ^
    --rm ^
    disk-management-rar-processor

echo.
echo RAR processor is running at http://localhost:5001
echo You can now start the main application.
pause
