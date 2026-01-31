# Cerbos Troubleshooting Guide

## Common Issues and Solutions

### Issue: `just up` Fails

#### 1. Docker Permission Errors
**Symptoms:**
```
permission denied while trying to connect to the Docker daemon socket
```

**Solution:**
- Ensure Docker Desktop is running
- Check Docker socket permissions
- Try: `sudo docker compose up -d` (if on Linux)
- On macOS: Ensure Docker Desktop has proper permissions

#### 2. Cerbos Configuration Errors

**Check Configuration:**
```bash
# Validate compose.yml syntax
docker compose config

# Check if Cerbos config file exists
test -f cerbos/cerbos.yaml && echo "OK" || echo "Missing"

# Check if policies directory exists
ls -la cerbos/policies/resource_policies/
```

**Common Config Issues:**
- Missing `cerbos.yaml` file
- Incorrect YAML syntax
- Wrong storage driver configuration

**Verify Cerbos Config Format:**
The `cerbos.yaml` should have:
```yaml
storage:
  driver: "disk"
  disk:
    directory: /policies
    watchForChanges: true
```

#### 3. Missing Policy Files

**Check:**
```bash
# Verify policy files exist
ls cerbos/policies/resource_policies/*.yaml
ls cerbos/policies/_schemas/*.json
```

**Required Files:**
- `cerbos/policies/resource_policies/postgres.yaml`
- `cerbos/policies/resource_policies/iceberg.yaml`
- `cerbos/policies/_schemas/principal.json`
- `cerbos/policies/_schemas/resource.json`

#### 4. Adapter Build Failures

**Check:**
```bash
# Verify adapter files exist
ls -la cerbos-adapter/

# Should have:
# - Dockerfile
# - adapter.py
# - requirements.txt
```

**Build Manually:**
```bash
cd cerbos-adapter
docker build -t cerbos-adapter-test .
```

#### 5. Port Conflicts

**Check if ports are in use:**
```bash
# Check port 3593 (Cerbos)
lsof -i :3593 || echo "Port 3593 available"

# Check port 3594 (Adapter)
lsof -i :3594 || echo "Port 3594 available"
```

**Solution:**
- Stop services using these ports
- Or update ports in `compose.yml`

### Issue: Cerbos Service Won't Start

#### Check Logs
```bash
docker compose logs cerbos
```

#### Common Errors:

**1. Config File Not Found**
```
Error: open /config/cerbos.yaml: no such file or directory
```
**Solution:** Ensure `cerbos/cerbos.yaml` exists and is mounted correctly

**2. Policies Directory Not Found**
```
Error: policies directory not found
```
**Solution:** Ensure `cerbos/policies/` directory exists

**3. Invalid Policy Syntax**
```
Error: failed to compile policy
```
**Solution:** Validate policies:
```bash
# If Cerbos CLI installed
cerbos compile cerbos/policies

# Or via Docker
docker run --rm -v $(pwd)/cerbos/policies:/policies \
  ghcr.io/cerbos/cerbos:latest compile /policies
```

### Issue: Adapter Service Won't Start

#### Check Logs
```bash
docker compose logs cerbos-adapter
```

#### Common Errors:

**1. Python Import Errors**
```
ModuleNotFoundError: No module named 'fastapi'
```
**Solution:** Ensure `requirements.txt` is correct and image is rebuilt

**2. Connection to Cerbos Fails**
```
Connection refused: cerbos:3593
```
**Solution:** 
- Ensure Cerbos is healthy: `just check-cerbos`
- Check network connectivity
- Verify `CERBOS_URL` environment variable

**3. Health Check Fails**
```
Health check failed
```
**Solution:**
- Ensure curl is installed in adapter image
- Check adapter is listening on port 8080
- Verify health endpoint: `curl http://localhost:3594/health`

### Issue: Envoy Can't Connect to Adapter

#### Check Logs
```bash
docker compose logs envoy
```

#### Common Errors:

**1. Adapter Not Ready**
```
upstream connect error or disconnect/reset before headers
```
**Solution:**
- Ensure adapter is healthy: `just check-cerbos-adapter`
- Check adapter logs: `docker compose logs cerbos-adapter`
- Verify adapter is on the same network

**2. Wrong Adapter URL**
```
connection refused
```
**Solution:** Check `envoy/envoy.yaml` has correct adapter URL:
```yaml
uri: http://cerbos-adapter:8080
```

### Debugging Steps

1. **Check All Services Status**
   ```bash
   docker compose ps
   ```

2. **Check Service Health**
   ```bash
   just check-cerbos
   just check-cerbos-adapter
   ```

3. **View All Logs**
   ```bash
   docker compose logs
   ```

4. **Restart Services**
   ```bash
   docker compose restart cerbos cerbos-adapter envoy
   ```

5. **Rebuild Adapter**
   ```bash
   docker compose build cerbos-adapter
   docker compose up -d cerbos-adapter
   ```

### Validation Commands

```bash
# Validate compose.yml
docker compose config

# Validate Cerbos policies (if CLI installed)
just validate-cerbos-policies

# Test Cerbos health
curl http://localhost:3593/_cerbos/health

# Test adapter health
curl http://localhost:3594/health

# Test authorization (through adapter)
curl -X POST http://localhost:3594/check \
  -H "Content-Type: application/json" \
  -d '{"attributes":{"request":{"http":{"method":"POST","path":"/v1/statement","headers":{"x-user-id":"1","x-user-email":"test@example.com","x-user-roles":"admin"},"body":"SELECT 1"}}}}'
```

### Getting Help

1. Check service logs: `docker compose logs <service-name>`
2. Verify configuration files exist and are correct
3. Ensure all required directories exist
4. Check network connectivity between services
5. Verify ports are not in use
