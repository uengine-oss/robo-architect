/**
 * Which runtime configuration a runtime manifest describes (FABRIC-SPLIT.md 3.1).
 *
 *   ontological  (default, a manifest without `deployVariant`) — compose.yml: the Ontological DB
 *                (graph-db + graph-bolt) holds the graph and the data fabric, robo-data-fabric in front.
 *   age-fabric   compose.age-fabric.yml: Apache AGE behind our Bolt gateway (age-db + age-bolt) for the
 *                graph, the fabric service og-fabric with its own PG (fabric + fabric-db) for the sources.
 *
 * Pure (no Electron): docker-stack.ts and the tests read it.
 */

export type DeployVariant = "ontological" | "age-fabric";

export const DEFAULT_VARIANT: DeployVariant = "ontological";

/** The compose project of the default configuration (unchanged). */
export const DEFAULT_COMPOSE_PROJECT_NAME = "robo-architect-desktop";

/**
 * age-fabric runs as its own project so the default stack's containers are never recreated with the
 * other configuration (and the plaintext migration can still reach the default stack's graph-db).
 */
export const AGE_FABRIC_COMPOSE_PROJECT_NAME = "robo-architect-desktop-age";

const BASE_IMAGES = ["graphDb", "graphBolt", "analyzer", "catalog", "fabric", "parser", "gateway", "wireframe"] as const;

export type BaseImageKey = (typeof BASE_IMAGES)[number];
export type ImageKey = BaseImageKey | "fabricDb";

export function deployVariantOf(raw: unknown): DeployVariant {
  if (raw === undefined || raw === null || raw === "" || raw === "ontological") return "ontological";
  if (raw === "age-fabric") return "age-fabric";
  throw new Error(`runtime.manifest_invalid: deployVariant ${JSON.stringify(raw)} (ontological | age-fabric)`);
}

/** The images a manifest of this configuration must name. */
export function requiredImageKeys(variant: DeployVariant): ImageKey[] {
  return variant === "age-fabric" ? [...BASE_IMAGES, "fabricDb"] : [...BASE_IMAGES];
}

export interface VariantServices {
  /** the graph's PostgreSQL service */
  db: string;
  /** the Bolt gateway service */
  bolt: string;
  /** the fabric's PostgreSQL service (age-fabric only) */
  fabricDb: string | null;
}

export function servicesOf(variant: DeployVariant): VariantServices {
  return variant === "age-fabric"
    ? { db: "age-db", bolt: "age-bolt", fabricDb: "fabric-db" }
    : { db: "graph-db", bolt: "graph-bolt", fabricDb: null };
}

const PROJECT_NAME = /^[a-z0-9][a-z0-9_-]{0,62}$/;

/** ROBO_COMPOSE_PROJECT when it is a valid compose project name, else the configuration's own. */
export function composeProjectName(variant: DeployVariant, override: string | undefined): string {
  if (override && PROJECT_NAME.test(override)) return override;
  return variant === "age-fabric" ? AGE_FABRIC_COMPOSE_PROJECT_NAME : DEFAULT_COMPOSE_PROJECT_NAME;
}
