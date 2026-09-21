import { config } from "dotenv";
import { fileURLToPath } from "node:url";
import { z } from "zod";

const rootEnvPath = fileURLToPath(
  new URL("../../../../.env", import.meta.url)
);

const result = config({
  path: rootEnvPath
});

if (result.error) {
  throw new Error(
    `Unable to load Origin Hut root environment from ${rootEnvPath}`
  );
}

const envSchema = z.object({

  NODE_ENV: z
    .enum([
      "development",
      "test",
      "production"
    ])
    .default("development"),

  API_HOST: z
    .string()
    .default("0.0.0.0"),

  API_PORT: z
    .coerce
    .number()
    .int()
    .positive()
    .default(4000),

  DATABASE_URL: z
    .string()
    .min(1)

});

export const env = envSchema.parse(process.env);
