const http = require('node:http');
const path = require('node:path');
const fs = require('node:fs');

const host = '127.0.0.1';
const defaultPort = 4173;
const siteRoot = path.resolve(__dirname, '../test-site');

function readPort(value) {
  if (value === undefined || value === '') {
    return defaultPort;
  }

  const port = Number(value);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error('BROWSER_QA_PORT must be an integer between 1 and 65535.');
  }
  return port;
}

const port = readPort(process.env.BROWSER_QA_PORT);

function send(response, statusCode, body, contentType = 'text/plain; charset=utf-8') {
  response.writeHead(statusCode, {
    'Content-Type': contentType,
    'Content-Length': Buffer.byteLength(body),
    'X-Content-Type-Options': 'nosniff',
  });
  response.end(body);
}

function isOutsideSite(candidatePath) {
  const relativePath = path.relative(siteRoot, candidatePath);
  return relativePath === '..'
    || relativePath.startsWith(`..${path.sep}`)
    || path.isAbsolute(relativePath);
}

const server = http.createServer((request, response) => {
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    response.setHeader('Allow', 'GET, HEAD');
    send(response, 405, 'Method Not Allowed\n');
    return;
  }

  let pathname;
  try {
    pathname = decodeURIComponent(new URL(request.url, `http://${host}`).pathname);
  } catch {
    send(response, 400, 'Bad Request\n');
    return;
  }

  if (pathname === '/healthz') {
    send(response, 200, 'ok\n');
    return;
  }

  if (pathname.includes('\0')) {
    send(response, 400, 'Bad Request\n');
    return;
  }

  const filePath = path.resolve(siteRoot, `.${pathname}`);
  if (isOutsideSite(filePath)) {
    send(response, 403, 'Forbidden\n');
    return;
  }

  fs.realpath(filePath, (realPathError, resolvedFilePath) => {
    if (realPathError) {
      send(response, 404, 'Not Found\n');
      return;
    }

    if (isOutsideSite(resolvedFilePath)) {
      send(response, 403, 'Forbidden\n');
      return;
    }

    fs.stat(resolvedFilePath, (statError, stats) => {
      if (statError || !stats.isFile()) {
        send(response, 404, 'Not Found\n');
        return;
      }

      response.writeHead(200, {
        'Content-Type': path.extname(resolvedFilePath) === '.html'
          ? 'text/html; charset=utf-8'
          : 'application/octet-stream',
        'Content-Length': stats.size,
        'X-Content-Type-Options': 'nosniff',
      });

      if (request.method === 'HEAD') {
        response.end();
        return;
      }

      const stream = fs.createReadStream(resolvedFilePath);
      stream.on('error', () => {
        if (!response.headersSent) {
          send(response, 500, 'Internal Server Error\n');
        } else {
          response.destroy();
        }
      });
      stream.pipe(response);
    });
  });
});

server.listen(port, host, () => {
  console.log(`Browser QA test site listening at http://${host}:${port}`);
});

function shutDown(signal) {
  console.log(`Received ${signal}; shutting down.`);
  process.removeAllListeners('SIGINT');
  process.removeAllListeners('SIGTERM');
  server.close((error) => {
    process.exitCode = error ? 1 : 0;
  });
}

process.on('SIGINT', () => shutDown('SIGINT'));
process.on('SIGTERM', () => shutDown('SIGTERM'));
