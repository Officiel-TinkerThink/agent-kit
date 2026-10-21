// macOS: npm starts directly and the Playwright browser starts without extra system libraries. Root is a POSIX root.
import { rootRisk } from "./posix.mjs";

export default { name: "darwin", npmNeedsShell: false, rootRisk, ensureBrowser() {} };
