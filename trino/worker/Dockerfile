FROM trinodb/trino:474

# Wipe the built-in etc to avoid any chance of precedence shenanigans
RUN rm -rf /usr/lib/trino/etc/*

# Install ONLY your configs
COPY config.properties /etc/trino/config.properties
COPY node.properties   /etc/trino/node.properties
COPY jvm.config        /etc/trino/jvm.config
COPY log.properties    /etc/trino/log.properties

# (Optional) add a tiny entrypoint preflight to show what is read
COPY show-config-and-run.sh /usr/local/bin/show-config-and-run.sh
ENTRYPOINT ["/usr/local/bin/show-config-and-run.sh"] 