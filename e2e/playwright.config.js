// @ts-check
const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["json", { outputFile: "results.json" }], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.BASE_URL || "http://localhost:8080",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});
