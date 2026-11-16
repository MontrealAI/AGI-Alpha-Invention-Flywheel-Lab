"""Pinned, exact-host HTTPS transport. No redirects, localhost or DNS rebinding."""
import http.client
import ipaddress
import json
import socket
from urllib.parse import urlsplit
from .core import parse,harness


def request(method,url,headers=None,body=None,*,hosts=()):
    u=urlsplit(url)
    if u.scheme!='https' or u.hostname not in hosts or u.port not in (None,443) or u.username or u.password or u.fragment or any(c in url for c in '\r\n\x00'):
        raise ValueError('AUTHORIZED_HTTPS_ENDPOINT_REQUIRED')
    addresses={r[4][0] for r in socket.getaddrinfo(u.hostname,443,type=socket.SOCK_STREAM)}
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):raise ValueError('PUBLIC_ADDRESS_REQUIRED')
    conn=harness('adapters').PinnedHTTPS(u.hostname,sorted(addresses)[0],30)
    try:
        conn.request(method,(u.path or '/')+('?' + u.query if u.query else ''),body=body,headers=headers or {})
        response=conn.getresponse();data=response.read(2_000_001)
        if len(data)>2_000_000:raise ValueError('BOUNDED_REMOTE_RESPONSE_REQUIRED')
        if response.status==202:return {'pending':True}
        if response.status not in (200,201):raise ValueError('REMOTE_STATUS_'+str(response.status))
        return parse(data)
    finally:conn.close()
