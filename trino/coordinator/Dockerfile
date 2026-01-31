FROM trinodb/trino:474

# Install your configs (overwrite the default ones)
COPY config.properties /etc/trino/config.properties
COPY node.properties   /etc/trino/node.properties
COPY jvm.config        /etc/trino/jvm.config
COPY log.properties    /etc/trino/log.properties
COPY access-control.properties /etc/trino/access-control.properties
COPY column-masks.properties /etc/trino/column-masks.properties

# Use the standard Trino entrypoint
ENTRYPOINT ["/usr/lib/trino/bin/launcher", "run"] 