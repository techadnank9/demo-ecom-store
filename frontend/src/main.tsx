import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

// Keeping the browser on one origin makes the same workflow portable between
// Docker, Render, and a developer's laptop. Nginx forwards /api to FastAPI.
const API_URL = import.meta.env.VITE_API_URL || "";
const product = {
  id: "kinetic-driver-01",
  name: "Kinetic Driver",
  price_cents: 12900,
};

function getRunId() {
  return new URLSearchParams(window.location.search).get("rf_run_id") || "manual-run";
}

function App() {
  const [cart, setCart] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [orderId, setOrderId] = useState("");
  const [error, setError] = useState("");

  async function checkout() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API_URL}/api/checkout`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-regressionforge-run-id": getRunId(),
        },
        body: JSON.stringify({
          customer_name: name,
          email,
          product_id: product.id,
          quantity: 1,
          total_cents: product.price_cents,
        }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.message || body.detail || "Checkout failed");
      setOrderId(body.order.id);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Checkout failed");
    } finally {
      setLoading(false);
    }
  }

  if (orderId) {
    return (
      <main className="confirmation" data-testid="confirmation-screen">
        <div className="confirmation-mark">✓</div>
        <p className="eyebrow">Payment accepted</p>
        <h1>Built to arrive.</h1>
        <p>Your Kinetic Driver is confirmed and headed to fulfillment.</p>
        <dl>
          <div><dt>Order</dt><dd data-testid="order-id">{orderId}</dd></div>
          <div><dt>Total</dt><dd>$129.00</dd></div>
          <div><dt>Status</dt><dd>Confirmed</dd></div>
        </dl>
        <span className="run-stamp">CERTIFICATION RUN / {getRunId().slice(0, 12)}</span>
      </main>
    );
  }

  return (
    <main>
      <nav>
        <a className="wordmark" href="#">FORGE<span>/</span>CART</a>
        <div className="nav-center"><a href="#tool">Shop</a><a href="#details">Field notes</a></div>
        <button className="cart-link" data-testid="cart-count">Bag {cart ? "01" : "00"}</button>
      </nav>

      <section className="product" id="tool">
        <div className="visual-plane" aria-label="Kinetic Driver product photograph">
          <div className="serial">KD–01 / BRUSHED STEEL</div>
          <div className="driver" aria-hidden="true">
            <div className="bit" />
            <div className="shaft" />
            <div className="collar" />
            <div className="handle"><i /><i /><i /><i /><i /></div>
          </div>
          <div className="spec-orbit">24T</div>
          <p className="visual-caption">Quarter-inch bit system<br />24-tooth sealed ratchet</p>
        </div>

        <div className="product-copy">
          <p className="eyebrow">Workbench series / 01</p>
          <h1>Kinetic<br />Driver</h1>
          <p className="lede">One precise instrument for the fixes that deserve your full attention.</p>
          <div className="purchase-line">
            <span>$129</span>
            <button data-testid="add-to-cart" onClick={() => setCart(true)}>
              {cart ? "Added to bag" : "Add to bag"}<b>↗</b>
            </button>
          </div>
          <div className="features" id="details">
            <span>Lifetime service</span><span>S2 steel bits</span><span>Ships in 24h</span>
          </div>
        </div>
      </section>

      {cart && (
        <aside className="checkout" data-testid="checkout-panel">
          <div className="checkout-head"><span>Secure checkout</span><button onClick={() => setCart(false)}>Close</button></div>
          <div className="line-item"><span>Kinetic Driver × 1</span><strong>$129.00</strong></div>
          <label>Full name<input data-testid="customer-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Avery Stone" /></label>
          <label>Email<input data-testid="customer-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="avery@example.com" /></label>
          {error && <p className="error" data-testid="checkout-error">{error}</p>}
          <button className="place-order" data-testid="place-order" disabled={!name || !email || loading} onClick={checkout}>
            {loading ? "Authorizing…" : "Place order"}<span>$129.00</span>
          </button>
          <p className="fine">Encrypted checkout · 30-day workshop trial</p>
        </aside>
      )}
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
