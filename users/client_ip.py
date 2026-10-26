def get_client_ip(request):
    """
    Return the visitor's real IP.
    Behind Cloudflare Tunnel, every request arrives from 127.0.0.1,
    so we read the CF-Connecting-IP header that Cloudflare adds.
    Falls back to REMOTE_ADDR for local development without the tunnel.
    """
    return (
        request.META.get("HTTP_CF_CONNECTING_IP")
        or request.META.get("REMOTE_ADDR")
    )