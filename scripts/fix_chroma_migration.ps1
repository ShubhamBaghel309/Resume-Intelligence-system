# Quick fix for Chroma migration error
# Run this if you see: "You are using a deprecated configuration of Chroma"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "🔧 CHROMA MIGRATION FIX" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Step 1: Remove deprecated environment variables
Write-Host "Step 1: Removing deprecated Chroma variables..." -ForegroundColor Yellow

[System.Environment]::SetEnvironmentVariable('CHROMA_DB_IMPL', $null, 'User')
[System.Environment]::SetEnvironmentVariable('CHROMA_PERSIST_DIRECTORY', $null, 'User')

# Also unset in current session
$env:CHROMA_DB_IMPL = $null
$env:CHROMA_PERSIST_DIRECTORY = $null

Write-Host "   ✅ Removed CHROMA_DB_IMPL" -ForegroundColor Green
Write-Host "   ✅ Removed CHROMA_PERSIST_DIRECTORY`n" -ForegroundColor Green

# Step 2: Set correct cache directories
Write-Host "Step 2: Setting cache directories to D drive..." -ForegroundColor Yellow

$env:HF_HOME = "D:\cache\hugging_face"
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"

Write-Host "   ✅ HF_HOME = D:\cache\hugging_face" -ForegroundColor Green
Write-Host "   ✅ Symlink warnings disabled`n" -ForegroundColor Green

# Step 3: Backup old data (if exists)
Write-Host "Step 3: Backing up old Chroma data..." -ForegroundColor Yellow

if (Test-Path "storage\chroma") {
    if (Test-Path "storage\chroma_backup") {
        Remove-Item -Recurse -Force "storage\chroma_backup"
    }
    Move-Item "storage\chroma" "storage\chroma_backup"
    Write-Host "   ✅ Old data backed up to storage\chroma_backup`n" -ForegroundColor Green
} else {
    Write-Host "   ⚠️  No old data found (starting fresh)`n" -ForegroundColor Yellow
}

# Step 4: Re-index all resumes
Write-Host "Step 4: Re-indexing all resumes..." -ForegroundColor Yellow
Write-Host "   This will take a few minutes...`n" -ForegroundColor Cyan

python scripts\index_all_resumes.py

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "✅ CHROMA FIX COMPLETE!" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "💡 What was fixed:" -ForegroundColor Yellow
Write-Host "   - Removed deprecated CHROMA_DB_IMPL variable"
Write-Host "   - Old data backed up to storage\chroma_backup"
Write-Host "   - All resumes re-indexed with new Chroma format"
Write-Host "   - Cache directories now on D drive"

Write-Host "`n⚠️  IMPORTANT: Restart your terminal/IDE for changes to persist!" -ForegroundColor Yellow
Write-Host "   After restart, you can use the system normally.`n"
