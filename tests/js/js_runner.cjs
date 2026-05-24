"use strict";
// Node.js test runner for js_pure generated code.
// Usage: node js_runner.cjs <html_file> <class_name>
// Generated JS code is read from stdin.

const { JSDOM } = require("jsdom");
const fs = require("fs");

const htmlFile = process.argv[2];
const className = process.argv[3];

const html = fs.readFileSync(htmlFile, "utf-8");
const { window } = new JSDOM(html, { url: "http://localhost" });

// Provide browser globals that generated code expects
global.document = window.document;
global.DOMParser = window.DOMParser;
global.XPathResult = window.XPathResult;

// Read generated code from stdin
let code = "";
process.stdin.setEncoding("utf-8");
process.stdin.on("data", (chunk) => (code += chunk));
process.stdin.on("end", () => {
  try {
    const fn = new Function(code + `\nreturn ${className};`);
    const Cls = fn();
    const result = new Cls(html).parse();
    console.log(JSON.stringify(result));
  } catch (e) {
    process.stderr.write(e.toString() + "\n");
    process.exit(1);
  }
});
