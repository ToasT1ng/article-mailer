import cron from "node-cron";
import { loadSettings } from "./settings.js";
import { runPipeline } from "./pipeline.js";
import logger from "./logger.js";

const log = logger.child({ module: "index" });

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const runNow = args.includes("--run-now");
  const dryRun = args.includes("--dry-run");
  const countIdx = args.indexOf("--count");
  const countOverride = countIdx !== -1 ? parseInt(args[countIdx + 1], 10) : undefined;

  const settings = loadSettings();
  if (countOverride !== undefined && !isNaN(countOverride)) {
    settings.ARTICLE_COUNT = countOverride;
  }

  if (runNow || dryRun) {
    log.info({ event: "index.run_now", dryRun });
    await runPipeline(settings, { dryRun });
    process.exit(0);
  }

  const cronExpr = `${settings.SEND_MINUTE} ${settings.SEND_HOUR} * * *`;
  log.info({ event: "index.scheduler_start", cron: cronExpr, timezone: settings.TIMEZONE });

  cron.schedule(
    cronExpr,
    async () => {
      log.info({ event: "index.cron_triggered" });
      try {
        await runPipeline(settings);
      } catch (err) {
        log.error({ event: "index.cron_error", error: String(err) });
      }
    },
    { timezone: settings.TIMEZONE }
  );
}

main().catch((err) => {
  logger.error({ event: "index.fatal", error: String(err) });
  process.exit(1);
});
