FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /build
COPY pom.xml ./
COPY src ./src
RUN mvn -B -DskipTests package
FROM eclipse-temurin:17-jre-jammy
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/* \
    && groupadd -g 10001 dodam && useradd -u 10001 -g dodam -m dodam \
    && mkdir -p /data/object-storage && chown dodam:dodam /data/object-storage
WORKDIR /app
COPY --from=build /build/target/dodam-0.0.1-SNAPSHOT.jar /app/app.jar
USER 10001:10001
ENTRYPOINT ["java", "-XX:MaxRAMPercentage=65", "-jar", "/app/app.jar"]
