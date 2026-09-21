import Fastify from "fastify";
import cors from "@fastify/cors";

import { env } from "./config/env.js";

import {
  checkDatabase,
  database
} from "./lib/database.js";

import {
  databaseRoutes
} from "./routes/database.js";

import {
  referenceRoutes
} from "./routes/reference.js";

import {
  classificationRoutes
} from "./routes/classification.js";

import {
  productRoutes
} from "./routes/products.js";


const app = Fastify({
  logger: true
});


await app.register(cors, {
  origin: true
});


await app.register(
  databaseRoutes
);

await app.register(
  referenceRoutes
);

await app.register(
  classificationRoutes
);

await app.register(
  productRoutes
);


app.get(
  "/api/health/live",
  async () => {

    return {

      ok: true,

      service: "origin-hut-api",

      status: "alive",

      timestamp:
        new Date().toISOString()

    };

  }
);


app.get(
  "/api/health",
  async (
    _request,
    reply
  ) => {

    const db =
      await checkDatabase();

    if (!db.connected) {
      reply.code(503);
    }

    return {

      ok:
        db.connected,

      service:
        "origin-hut-api",

      platform:
        "Origin Hut",

      domain:
        "export-import",

      environment:
        env.NODE_ENV,

      database:
        db,

      timestamp:
        new Date().toISOString()

    };

  }
);


app.get(
  "/api/health/ready",
  async (
    _request,
    reply
  ) => {

    const db =
      await checkDatabase();

    if (!db.connected) {

      reply.code(503);

      return {

        ready:
          false,

        database:
          db,

        timestamp:
          new Date().toISOString()

      };

    }

    return {

      ready:
        true,

      database:
        db,

      timestamp:
        new Date().toISOString()

    };

  }
);


async function shutdown(
  signal: string
) {

  app.log.info(
    {
      signal
    },
    "Origin Hut shutting down"
  );

  await app.close();

  await database.end();

  process.exit(0);

}


process.on(
  "SIGINT",
  () => {
    void shutdown(
      "SIGINT"
    );
  }
);


process.on(
  "SIGTERM",
  () => {
    void shutdown(
      "SIGTERM"
    );
  }
);


try {

  await app.listen({

    port:
      env.API_PORT,

    host:
      env.API_HOST

  });

  app.log.info(
    {
      service:
        "origin-hut-api",

      environment:
        env.NODE_ENV,

      port:
        env.API_PORT,

      host:
        env.API_HOST
    },
    "Origin Hut API started"
  );

}
catch (error) {

  app.log.error(
    error
  );

  await database.end();

  process.exit(1);

}
