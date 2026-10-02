"use strict";
// Persistent Node.js worker for js_pure generated code testing.
// Listens on stdin for JSON requests: { id, code, className, html }
// Emits single-line JSON responses on stdout: { id, ok: true, result } or { id, ok: false, error }

const { JSDOM } = require("jsdom");
const readline = require("readline");

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
  terminal: false,
});

rl.on("line", (line) => {
  if (!line.trim()) return;
  let req;
  try {
    req = JSON.parse(line);
    const { window } = new JSDOM(req.html, { url: "http://localhost" });
    global.document = window.document;
    global.DOMParser = window.DOMParser;
    global.XPathResult = window.XPathResult;
    global.window = window;

    const fn = new Function(req.code + "\nreturn " + req.className + ";");
    const Cls = fn();
    const result = new Cls(req.html).parse();
    console.log(JSON.stringify({ id: req.id, ok: true, result: result }));
  } catch (err) {
    console.log(JSON.stringify({ id: req ? req.id : null, ok: false, error: err.toString() }));
  }
});
