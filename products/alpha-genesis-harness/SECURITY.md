# Security and responsible operation

The primary security boundary is deliberately narrow: the core browser application interprets a declared bounded language and treats model responses and imported projects as data. It must not execute arbitrary JavaScript, Python, shell commands or HTML supplied by a model. A future executable-code integration needs a separately reviewed isolated executor with externally enforced resources and permissions.

Use only your own trusted copy of the application. A hostile extension, modified local application, compromised operating system or compromised provider is outside the application's ability to secure. Do not open private projects on a shared device. Project exports and browser storage are not encrypted.

The optional bridge must bind to loopback, validate its local request origin and host, and require its session authorization. Keep its config outside the downloaded product folder and outside source control. Set provider credentials through the environment; never paste a key into a mission, project, prompt, screenshot, issue or report. See `bridge/README.md` for the implemented boundary and known limitations.

Model responses, retrieved pages, copied examples and source citations are untrusted. A retrieved source can contain malicious instructions or inaccurate claims. They must not expand permissions or change the independent acceptance standard. A provider error or missing price must not be interpreted as a free successful call. Cancellation stops further local work where supported; it cannot guarantee cancellation of a request already accepted by an external provider or reverse a charge.

For a potential vulnerability, contact the project's public data-protection contact, **president@quebec.ai**, with a minimal description and a safe reproduction. Do not include credentials or customer data. This contact is published on the QUÉBEC.AI website; no response-time, remediation-time or paid-support guarantee is implied. If that route is unavailable, open a GitHub issue containing only a non-sensitive description and request a private follow-up channel.

No independently certified penetration test, secure enclave, encrypted project storage or signed desktop application is claimed for this candidate.
