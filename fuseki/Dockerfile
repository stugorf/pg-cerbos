FROM maven:3.9-eclipse-temurin-21 AS build

ARG JENA_VERSION=5.3.0
RUN mvn -q dependency:copy \
    -Dartifact=org.apache.jena:jena-fuseki-server:${JENA_VERSION}:jar \
    -DoutputDirectory=/tmp

FROM eclipse-temurin:21-jre

WORKDIR /app
COPY --from=build /tmp/jena-fuseki-server-*.jar /app/fuseki-server.jar
EXPOSE 3030
ENTRYPOINT ["java", "-jar", "/app/fuseki-server.jar"]
