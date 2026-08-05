# MongoDB Docker Startup Issue (WiredTiger Permission Error)

## Overview

The MongoDB container failed to start when using a bind mount to persist
database files:

``` yaml
volumes:
  - ./mongodb:/data/db
```

The goal was to keep MongoDB data inside the project folder instead of
using a Docker named volume.

------------------------------------------------------------------------

## Symptoms

-   MongoDB container continuously restarted.
-   MongoDB Compass returned:

``` text
ECONNREFUSED 127.0.0.1:27000
```

-   Docker logs showed:

``` text
/data/db/WiredTiger.wt
Operation not permitted
```

followed by:

``` text
Failed to start up WiredTiger
Terminating
```

------------------------------------------------------------------------

## Investigation

The following were verified:

-   Docker networking
-   Port mapping
-   MongoDB connection string
-   Windows folder permissions

Windows permissions were updated using:

``` powershell
icacls ".\docker\mongodb" /grant "${env:USERNAME}:(OI)(CI)F" /T
```

The command completed successfully, but the problem still existed.

------------------------------------------------------------------------

## Linux Permission Fix (Attempted)

When using bind mounts from a Linux filesystem, the recommended
permission fix is:

``` bash
docker run --rm mongo:7.0-jammy id mongodb

sudo chown -R 999:999 docker/mongodb
sudo chmod -R 770 docker/mongodb
```

This ensures that the MongoDB process inside the container owns the
mounted directory.

> Note: This approach is effective when the project is located on a
> native Linux filesystem (for example under `/home/...`). In this case,
> however, the project was located on a Windows drive (`D:`) accessed
> through Docker Desktop, so Linux ownership changes were not the root
> cause.

------------------------------------------------------------------------

## Final Solution

MongoDB was started with the following command:

``` yaml
command: mongod --dbpath /data/db --directoryperdb
```

Final configuration:

``` yaml
services:
  mongodb:
    image: mongo:7.0-jammy
    container_name: mongodb

    ports:
      - "27000:27017"

    volumes:
      - ./mongodb:/data/db

    command: mongod --dbpath /data/db --directoryperdb

    restart: always
```

------------------------------------------------------------------------

## Command Explanation

-   `mongod` --- Starts the MongoDB server.
-   `--dbpath /data/db` --- Stores all database files in `/data/db`.
-   `--directoryperdb` --- Creates a separate directory for each
    database while keeping shared WiredTiger files in the root of the
    data directory.

Because of the bind mount:

``` yaml
volumes:
  - ./mongodb:/data/db
```

all database files continue to be stored locally in the project's
`./mongodb` folder.

------------------------------------------------------------------------

## Result

-   MongoDB started successfully.
-   The container remained running.
-   MongoDB Compass connected successfully.
-   Database files continued to be stored inside the project's
    `./mongodb` directory.
