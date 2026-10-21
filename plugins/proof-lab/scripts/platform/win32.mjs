// Windows: npm is npm.cmd, so it needs a shell. The Playwright browser starts without extra system libraries.
export default { name: "win32", npmNeedsShell: true, ensureBrowser() {} };
