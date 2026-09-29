# 1️⃣ Login – get a JWT
$response = Invoke-RestMethod -Method Post `
    -Uri http://127.0.0.1:8000/api/admin/login `
    -Body @{username='admin'; password='admin123'} `
    -ContentType 'application/x-www-form-urlencoded'
$token = $response.access_token
Write-Host "Token: $token"

# 2️⃣ Read current config
$config = Invoke-RestMethod -Headers @{Authorization="Bearer $token"} `
    -Uri http://127.0.0.1:8000/api/admin/config
Write-Host "Config before:" $config

# 3️⃣ Update config
$update = @{model='openai/gpt-4o-mini'; system_prompt='Updated prompt'}
$updated = Invoke-RestMethod -Method Put `
    -Headers @{Authorization="Bearer $token"} `
    -Uri http://127.0.0.1:8000/api/admin/config `
    -Body ($update | ConvertTo-Json) `
    -ContentType 'application/json'
Write-Host "Config after:" $updated