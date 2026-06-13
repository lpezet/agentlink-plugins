module.exports = {
  // Reachable only from the proxy on the `secure` network.
  // cred-gateway does not whitelist this path, so dev cannot reach it.
  "/fal/key": async (url, send) => {
    console.log("[broker] issued fal key to proxy");
    send(200, { key: process.env.FAL_KEY });
  },
};
