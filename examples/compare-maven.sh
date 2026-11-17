#!/bin/sh
# Reference only: never called by the analyzer. Requires Maven and a JDK.
set -eu
case "${1:-}" in
    junit) group=junit; artifact=junit; version=4.13.2 ;;
    text) group=org.apache.commons; artifact=commons-text; version=1.12.0 ;;
    slf4j) group=org.slf4j; artifact=slf4j-simple; version=2.0.13 ;;
    *) echo "usage: sh examples/compare-maven.sh junit|text|slf4j [tree|resolve]" >&2
       exit 2 ;;
esac
goal=${2:-tree}
case "$goal" in
    tree|resolve) ;;
    *) echo "expected tree or resolve" >&2; exit 2 ;;
esac
folder=$(mktemp -d)
trap 'rm -r "$folder"' EXIT
cat > "$folder/pom.xml" <<EOF
<project>
  <modelVersion>4.0.0</modelVersion>
  <groupId>edu.demo</groupId>
  <artifactId>maven-reference</artifactId>
  <version>1.0</version>
  <dependencies>
    <dependency>
      <groupId>$group</groupId>
      <artifactId>$artifact</artifactId>
      <version>$version</version>
    </dependency>
  </dependencies>
</project>
EOF
mvn -B -f "$folder/pom.xml" \
    "org.apache.maven.plugins:maven-dependency-plugin:3.8.1:$goal" \
    -Dscope=runtime -DincludeScope=runtime
