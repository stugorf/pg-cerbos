FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /src
COPY pom.xml .
RUN mvn -q -DskipTests dependency:go-offline
COPY src ./src
RUN mvn -q package

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /src/target/graph-query-analyzer-0.1.0.jar /app/app.jar
EXPOSE 8080
CMD ["java", "-jar", "/app/app.jar"]
