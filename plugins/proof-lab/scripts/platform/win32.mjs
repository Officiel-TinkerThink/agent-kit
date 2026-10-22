// Windows: npm is npm.cmd, so it needs a shell. The Playwright browser starts without extra system libraries. There is no
// root user: an elevated prompt is not detected, so there is no warning to give.
export default { name: "win32", npmNeedsShell: true, rootRisk: () => "", othersCanChange: () => false, ensureBrowser() {} };
