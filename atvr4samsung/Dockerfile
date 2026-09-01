# Upstream 2.0.1 multi-architecture image, pinned to the digest published in
# atvr4samsung-2.0.1-release.env and its GitHub artifact attestation.
FROM ghcr.io/vb3/atvr4samsung@sha256:169d7766eaa0eb4de69cbd90d1aff65554bac782d1ac8902ed95ecd5d3824d6d

USER root

ENV ATVR4SAMSUNG_HAOS_VERSION=0.1.4

COPY build/apply_touch_compat_patch.py /usr/local/libexec/atvr4samsung-apply-touch-compat-patch.py
COPY build/verify_touch_compat.py /usr/local/libexec/atvr4samsung-verify-touch-compat.py
RUN python3 /usr/local/libexec/atvr4samsung-apply-touch-compat-patch.py
RUN python3 /usr/local/libexec/atvr4samsung-verify-touch-compat.py

COPY build/apply_watch_compat_patch.py /usr/local/libexec/atvr4samsung-apply-watch-compat-patch.py
COPY build/verify_watch_compat.py /usr/local/libexec/atvr4samsung-verify-watch-compat.py
RUN python3 /usr/local/libexec/atvr4samsung-apply-watch-compat-patch.py
RUN python3 /usr/local/libexec/atvr4samsung-verify-watch-compat.py

COPY build/apply_watch_input_patch.py /usr/local/libexec/atvr4samsung-apply-watch-input-patch.py
COPY build/verify_watch_input.py /usr/local/libexec/atvr4samsung-verify-watch-input.py
RUN python3 /usr/local/libexec/atvr4samsung-apply-watch-input-patch.py
RUN python3 /usr/local/libexec/atvr4samsung-verify-watch-input.py

COPY rootfs/usr/local/bin/haos_wrapper.py /usr/local/bin/haos_wrapper.py
RUN chmod 0755 /usr/local/bin/haos_wrapper.py

ENTRYPOINT ["python3", "/usr/local/bin/haos_wrapper.py"]
CMD []

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD ["python3", "/usr/local/bin/haos_wrapper.py", "healthcheck"]
