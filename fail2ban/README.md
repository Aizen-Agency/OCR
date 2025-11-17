# Fail2ban Configuration

Fail2ban automatically bans IP addresses that show malicious behavior by monitoring nginx access logs.

## Jails Configured

### nginx-auth
- **Purpose**: Ban IPs with authentication failures (401/403 responses)
- **Max Retries**: 5 failed attempts
- **Time Window**: 10 minutes
- **Ban Duration**: 1 hour
- **Log Path**: `/var/log/nginx/access.log`

### nginx-limit-req
- **Purpose**: Ban IPs that repeatedly hit rate limits (429 responses)
- **Max Retries**: 10 violations
- **Time Window**: 5 minutes
- **Ban Duration**: 30 minutes
- **Log Path**: `/var/log/nginx/access.log`

## Management Commands

### Check Fail2ban Status
```bash
docker exec ocr-fail2ban-1 fail2ban-client status
```

### Check Specific Jail Status
```bash
# Check nginx-auth jail
docker exec ocr-fail2ban-1 fail2ban-client status nginx-auth

# Check nginx-limit-req jail
docker exec ocr-fail2ban-1 fail2ban-client status nginx-limit-req
```

### View Banned IPs
```bash
docker exec ocr-fail2ban-1 fail2ban-client status nginx-auth | grep "Banned IP list"
```

### Unban an IP
```bash
# Unban from nginx-auth jail
docker exec ocr-fail2ban-1 fail2ban-client set nginx-auth unbanip <IP_ADDRESS>

# Unban from nginx-limit-req jail
docker exec ocr-fail2ban-1 fail2ban-client set nginx-limit-req unbanip <IP_ADDRESS>

# Unban from all jails
docker exec ocr-fail2ban-1 fail2ban-client unban <IP_ADDRESS>
```

### Manually Ban an IP
```bash
docker exec ocr-fail2ban-1 fail2ban-client set nginx-auth banip <IP_ADDRESS>
```

### Reload Configuration
```bash
docker exec ocr-fail2ban-1 fail2ban-client reload
```

## How It Works

1. Fail2ban monitors nginx access logs in real-time
2. When it detects authentication failures (401/403) or rate limit violations (429), it increments a counter for that IP
3. If an IP exceeds the max retry threshold within the findtime window, it gets banned
4. Banned IPs are blocked using iptables rules
5. After the bantime expires, the IP is automatically unbanned

## Logs

Fail2ban logs are available in the container:
```bash
docker exec ocr-fail2ban-1 tail -f /var/log/fail2ban.log
```

## Troubleshooting

### Fail2ban not banning IPs
1. Check if fail2ban is running: `docker exec ocr-fail2ban-1 fail2ban-client status`
2. Verify nginx logs are accessible: `docker exec ocr-fail2ban-1 ls -la /var/log/nginx/access.log`
3. Check fail2ban logs for errors: `docker exec ocr-fail2ban-1 tail -f /var/log/fail2ban.log`

### IPs not being detected
1. Verify log format matches the filter regex patterns
2. Check if nginx is logging to the expected location
3. Test the filter: `docker exec ocr-fail2ban-1 fail2ban-regex /var/log/nginx/access.log nginx-auth`

### Need to adjust ban times
Edit `fail2ban/jail.local` and restart the fail2ban container:
```bash
docker compose --profile production restart fail2ban
```

