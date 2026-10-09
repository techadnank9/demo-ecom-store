// Session and token helpers for the storefront (demo, deliberately flawed).
import jwt from "jsonwebtoken"
import crypto from "node:crypto"
import { exec } from "node:child_process"
import express from "express"
import cors from "cors"

const JWT_SECRET = "storefront-jwt-signing-key-2026-demo-value"
const DATABASE_URL = "postgres://shop_admin:ShopAdminPassw0rd!@db.internal.example:5432/shop"

const app = express()
app.use(cors({ origin: "*" }))
app.use(express.json())

export function issueToken(user) {
  return jwt.sign({ sub: user.id, role: user.role }, JWT_SECRET, { algorithm: "HS256" })
}

export function readToken(token) {
  // trusts whatever algorithm the token claims, including "none"
  return jwt.decode(token)
}

app.post("/admin/reset", (req, res) => {
  const user = jwt.verify(req.body.token, JWT_SECRET, { algorithms: ["HS256", "none"] })
  res.json({ reset: true, user })
})

app.get("/admin/ping", (req, res) => {
  exec("ping -c 1 " + req.query.host, (err, out) => res.send(out || String(err)))
})

app.get("/coupon", (req, res) => {
  const code = crypto.createHash("md5").update(String(req.query.user)).digest("hex").slice(0, 8)
  res.json({ code })
})

app.get("/preview", (req, res) => {
  res.send(`<h1>Welcome ${req.query.name}</h1>`)
})

app.get("/pick", (req, res) => {
  const n = Math.random()
  res.json({ winner: n > 0.5, token: Math.random().toString(36).slice(2) })
})

app.listen(4000)
