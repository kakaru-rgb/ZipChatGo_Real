FROM eclipse-temurin:21-jdk

WORKDIR /app

COPY . .

RUN chmod +x gradlew
RUN ./gradlew bootJar -x test

CMD ["sh", "-c", "java -jar $(find build/libs -name '*.jar' ! -name '*-plain.jar' -print -quit)"]