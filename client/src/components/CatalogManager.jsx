import { useEffect, useState } from "react";
import InventoryPanel from "./InventoryPanel";
import { api } from "../services/api";
import "./CatalogManager.css";

const emptyProduct = {
  name: "",
  description: "",
  category_id: "",
  price: "",
  cost: "",
};

function formatMoney(minor) {
  return new Intl.NumberFormat("en-KE", {
    style: "currency",
    currency: "KES",
  }).format(minor / 100);
}

export default function CatalogManager({ token, user, onSessionExpired }) {
  const isOwner = user.role === "owner";

  const [categories, setCategories] = useState([]);
  const [products, setProducts] = useState([]);
  const [categoryName, setCategoryName] = useState("");
  const [categoryId, setCategoryId] = useState(null);
  const [productForm, setProductForm] = useState(emptyProduct);
  const [productId, setProductId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function loadCatalog() {
      try {
        const [categoryData, productData] = await Promise.all([
          api("/categories", {
            token,
            signal: controller.signal,
          }),
          api("/products", {
            token,
            signal: controller.signal,
          }),
        ]);

        setCategories(categoryData);
        setProducts(productData);
      } catch (err) {
        if (err.name !== "AbortError") {
          setError(err.message);

          if (err.status === 401) {
            onSessionExpired(err.message);
          }
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    loadCatalog();

    return () => controller.abort();
  }, [token, onSessionExpired]);

  function resetCategory() {
    setCategoryId(null);
    setCategoryName("");
  }

  function resetProduct() {
    setProductId(null);
    setProductForm(emptyProduct);
  }

  function changeProduct(event) {
    const { name, value } = event.target;

    setProductForm((previous) => ({
      ...previous,
      [name]: value,
    }));
  }

  async function runChange(action) {
    setBusy(true);
    setError("");
    setNotice("");

    try {
      await action();
    } catch (err) {
      setError(err.message);

      if (err.status === 401) {
        onSessionExpired(err.message);
      }
    } finally {
      setBusy(false);
    }
  }

  function saveCategory(event) {
    event.preventDefault();

    runChange(async () => {
      const saved = await api(
        categoryId ? `/categories/${categoryId}` : "/categories",
        {
          method: categoryId ? "PATCH" : "POST",
          token,
          body: { name: categoryName },
        },
      );

      setCategories((previous) =>
        categoryId
          ? previous.map((category) =>
              category.id === saved.id ? saved : category,
            )
          : [...previous, saved],
      );

      // Reflect a renamed category in the product list.
      setProducts((previous) =>
        previous.map((product) =>
          product.category_id === saved.id
            ? { ...product, category_name: saved.name }
            : product,
        ),
      );

      resetCategory();
      setNotice("Category saved successfully.");
    });
  }

  function saveProduct(event) {
    event.preventDefault();

    runChange(async () => {
      const saved = await api(
        productId ? `/products/${productId}` : "/products",
        {
          method: productId ? "PUT" : "POST",
          token,
          body: {
            ...productForm,
            category_id: Number(productForm.category_id),
          },
        },
      );

      setProducts((previous) =>
        productId
          ? previous.map((product) =>
              product.id === saved.id ? saved : product,
            )
          : [...previous, saved],
      );

      resetProduct();
      setNotice("Product saved successfully.");
    });
  }

  function editProduct(product) {
    setProductId(product.id);
    setProductForm({
      name: product.name,
      description: product.description,
      category_id: String(product.category_id),
      price: (product.price_minor / 100).toFixed(2),
      cost: (product.cost_minor / 100).toFixed(2),
    });
    setError("");
    setNotice("");
  }

  function toggleProduct(product) {
    runChange(async () => {
      const saved = await api(`/products/${product.id}/status`, {
        method: "PATCH",
        token,
        body: { is_active: !product.is_active },
      });

      setProducts((previous) =>
        previous.map((item) => (item.id === saved.id ? saved : item)),
      );

      setNotice(
        saved.is_active ? "Product reactivated." : "Product deactivated.",
      );
    });
  }

  if (loading) {
    return <p role="status">Loading catalogue...</p>;
  }

  return (
    <section className="catalog">
      <h2>Categories and products</h2>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {notice && (
        <p className="success" role="status">
          {notice}
        </p>
      )}

      <h3>Categories</h3>

      {categories.length === 0 ? (
        <p>No categories yet.</p>
      ) : (
        <ul className="category-list">
          {categories.map((category) => (
            <li key={category.id}>
              <span>{category.name}</span>

              {isOwner && (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    setCategoryId(category.id);
                    setCategoryName(category.name);
                  }}
                >
                  Rename
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {isOwner && (
        <>
          <form className="auth-form" onSubmit={saveCategory}>
            <label htmlFor="category-name">
              {categoryId ? "Rename category" : "New category"}
            </label>
            <input
              id="category-name"
              required
              maxLength={100}
              value={categoryName}
              onChange={(event) => setCategoryName(event.target.value)}
            />

            <div className="catalog-actions">
              <button type="submit" disabled={busy}>
                {categoryId ? "Save category" : "Add category"}
              </button>

              {categoryId && (
                <button type="button" disabled={busy} onClick={resetCategory}>
                  Cancel
                </button>
              )}
            </div>
          </form>

          <h3>{productId ? "Edit product" : "Add product"}</h3>

          {categories.length === 0 && (
            <p>Create a category before adding a product.</p>
          )}

          <form className="auth-form" onSubmit={saveProduct}>
            <label htmlFor="product-name">Product name</label>
            <input
              id="product-name"
              name="name"
              required
              maxLength={150}
              value={productForm.name}
              onChange={changeProduct}
            />

            <label htmlFor="product-category">Category</label>
            <select
              id="product-category"
              name="category_id"
              required
              value={productForm.category_id}
              onChange={changeProduct}
            >
              <option value="">Select a category</option>
              {categories.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>

            <label htmlFor="product-description">Description</label>
            <textarea
              id="product-description"
              name="description"
              rows={3}
              maxLength={2000}
              value={productForm.description}
              onChange={changeProduct}
            />

            <label htmlFor="product-cost">Cost price (KSh)</label>
            <input
              id="product-cost"
              name="cost"
              type="number"
              min="0"
              max="100000000"
              step="0.01"
              required
              value={productForm.cost}
              onChange={changeProduct}
            />

            <label htmlFor="product-price">Selling price (KSh)</label>
            <input
              id="product-price"
              name="price"
              type="number"
              min="0"
              max="100000000"
              step="0.01"
              required
              value={productForm.price}
              onChange={changeProduct}
            />

            <div className="catalog-actions">
              <button type="submit" disabled={busy || categories.length === 0}>
                {productId ? "Save product" : "Add product"}
              </button>

              {productId && (
                <button type="button" disabled={busy} onClick={resetProduct}>
                  Cancel
                </button>
              )}
            </div>
          </form>
        </>
      )}

      <h3>Products ({products.length})</h3>

      {products.length === 0 ? (
        <p>No products available.</p>
      ) : (
        <div className="product-list">
          {products.map((product) => (
            <article className="product-card" key={product.id}>
              <h4>{product.name}</h4>
              <p>{product.category_name}</p>

              {product.description && <p>{product.description}</p>}

              <p>Selling price: {formatMoney(product.price_minor)}</p>

              {isOwner && (
                <>
                  <p>Cost price: {formatMoney(product.cost_minor)}</p>
                  <p>Status: {product.is_active ? "Active" : "Inactive"}</p>

                  <div className="catalog-actions">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => editProduct(product)}
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => toggleProduct(product)}
                    >
                      {product.is_active ? "Deactivate" : "Reactivate"}
                    </button>
                  </div>
                </>
              )}
              <InventoryPanel
                product={product}
                token={token}
                isOwner={isOwner}
                onSessionExpired={onSessionExpired}
              />
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
