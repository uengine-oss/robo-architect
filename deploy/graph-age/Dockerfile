# Robo 그래프 DB(AGE 판) — 일반 PostgreSQL 15 + Apache AGE 1.8.0
#
#   docker build -t ghcr.io/uengine-oss/robo-posco-graph-age:delivery deploy/graph-age
#
# 왜 Supabase Postgres 가 아닌가(2026-11-26): ontological-db `age/main` 의
# `age-supabase/` 는 Supabase 를 이미 쓰는 곳(Process GPT 등)에 붙이려고
# supabase/postgres 위에 AGE 를 얹었다. Robo 만 쓰는 곳(포스코)에는 그 이미지의
# 나머지 — pg_net(DB 가 밖으로 HTTP) · pg_cron · pgsodium · TimescaleDB 등 미리 올라오는
# 모듈 열세 개, Supabase 역할 열두 개, 3GB — 가 쓰이지 않고 SBOM · 취약점 심사에만 잡힌다.
# AGE 빌드 · 첫 실행 SQL 은 `age-supabase/`(builder/compile-age.sh · sql/99999999999999_age.sql)
# 를 그대로 옮겼다: 같은 AGE 커밋, 같은 `graph` DB(LC_COLLATE C), 같은 DROP 막이.
ARG PG_TAG=15.20-bookworm

FROM postgres:${PG_TAG} AS build
ARG AGE_REF=PG15/v1.8.0-rc0
ARG AGE_COMMIT=88646eb
RUN set -eux; \
    apt-get update -qq; \
    apt-get install -y -qq --no-install-recommends \
      build-essential flex bison perl git ca-certificates \
      "postgresql-server-dev-${PG_MAJOR}=${PG_VERSION}" >/dev/null; \
    git clone -q --depth 1 --branch "${AGE_REF}" https://github.com/apache/age.git /src; \
    cd /src; \
    commit="$(git rev-parse HEAD)"; \
    case "$commit" in "${AGE_COMMIT}"*) ;; *) echo "AGE 커밋이 다르다: $commit (기대 ${AGE_COMMIT})" >&2; exit 1;; esac; \
    make -j"$(nproc)" >/tmp/make.log 2>&1 || { tail -60 /tmp/make.log; exit 1; }; \
    make install DESTDIR=/stage >/dev/null; \
    strip --strip-debug "/stage/usr/lib/postgresql/${PG_MAJOR}/lib/age.so"; \
    printf 'age_ref=%s\nage_commit=%s\npg_version=%s\n' "${AGE_REF}" "$commit" "${PG_VERSION}" > /stage/BUILDINFO

FROM postgres:${PG_TAG}
ARG AGE_REF=PG15/v1.8.0-rc0
LABEL org.opencontainers.image.title="robo-graph-age" \
      org.opencontainers.image.description="PostgreSQL 15 + Apache AGE 1.8.0 for Robo Architect" \
      org.opencontainers.image.source="https://github.com/uengine-oss/robo-architect" \
      org.uengine.age.ref="${AGE_REF}"
COPY --from=build /stage/usr/lib/postgresql/ /usr/lib/postgresql/
COPY --from=build /stage/usr/share/postgresql/ /usr/share/postgresql/
COPY --from=build /stage/BUILDINFO /usr/share/postgresql/age-BUILDINFO
# initdb 가 이 견본을 새 볼륨의 postgresql.conf 로 복사한다 — compose 가 command 를 바꿔도 AGE 가 올라온다
RUN echo "shared_preload_libraries = 'age'" >> "/usr/share/postgresql/postgresql.conf.sample"
COPY 10-age.sql /docker-entrypoint-initdb.d/10-age.sql
