// macOS: npm starts directly and the Playwright browser starts without extra system libraries.
export default { name: "darwin", npmNeedsShell: false, ensureBrowser() {} };
