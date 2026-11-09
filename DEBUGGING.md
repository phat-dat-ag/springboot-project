# Docker Compose debugging

Normal startup does not configure JDWP:

```powershell
docker compose -p springboot_project -f docker-compose.yml up -d
```

Explicitly include the override to enable debugging for User, Learning and JWKS:

```powershell
docker compose -p springboot_project -f docker-compose.yml -f docker-compose.debug.yml config --quiet
docker compose -p springboot_project -f docker-compose.yml -f docker-compose.debug.yml up -d
```

The existing local project name is `springboot_project`. Use your own project
name if running a separate stack.

Set these values in the **root `.env`** or shell. Service-specific `env_file`
files supply container variables, not Compose interpolation values.

| Service | Port variable | Default | JVM options variable |
| --- | --- | --- | --- |
| User | `USER_API_DEBUG_PORT` | `5005` | `USER_API_JAVA_TOOL_OPTIONS` |
| Learning | `LEARNING_API_DEBUG_PORT` | `5006` | `LEARNING_API_JAVA_TOOL_OPTIONS` |
| JWKS | `JWKS_API_DEBUG_PORT` | `5007` | `JWKS_API_JAVA_TOOL_OPTIONS` |

Each port is used for both the host mapping and the container's JDWP listener.
Host bindings remain `127.0.0.1`; connect the IDE to `localhost` and the configured
port. Choose distinct available ports between 1 and 65535.

The default options are:

```text
-agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=*:<configured-port>
```

The root env examples derive the address from the corresponding port variable.
To add JVM options, preserve that JDWP argument and matching port, for example:

```dotenv
USER_API_DEBUG_PORT=15005
USER_API_JAVA_TOOL_OPTIONS=-Xmx512m -agentlib:jdwp=transport=dt_socket,server=y,suspend=n,address=*:${USER_API_DEBUG_PORT:-5005}
```

Shell variables take precedence over `.env`. The override supplies the default
JDWP options if its service-specific options variable is unset or empty. Empty
options therefore do not disable debugging.

There are no `DEBUG_ENABLED` flags: Compose cannot conditionally remove both JVM
options and published ports based on a boolean without additional machinery.
Omitting the override is the switch. Do not set a JDWP-enabled `JAVA_TOOL_OPTIONS`
directly in service env files if normal startup should remain free of debugging.

To disable debugging on containers previously started with the override, rerun
the normal startup command above. Compose recreates the affected API containers
with their base configuration; merely editing `.env` does not change running JVMs.
