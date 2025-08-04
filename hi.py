import numpy as np
import matplotlib.pyplot as plt
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split

# --------------------------
# Logistic Regression Utils
# --------------------------

def sigmoid(z):
    return 1 / (1 + np.exp(-z))

def initialize_parameters(dim):
    w = np.zeros((dim, 1))
    b = 0
    return w, b

def propagate(w, b, X, Y):
    m = X.shape[1]
    A = sigmoid(np.dot(w.T, X) + b)
    cost = -(1/m) * np.sum(Y*np.log(A) + (1 - Y)*np.log(1 - A))
    dw = (1/m) * np.dot(X, (A - Y).T)
    db = (1/m) * np.sum(A - Y)
    grads = {"dw": dw, "db": db}
    return grads, cost

def optimize(w, b, X, Y, num_iterations, learning_rate):
    costs = []
    print("\n🔁 Starting Backward Propagation (Training)...\n")
    for i in range(num_iterations):
        grads, cost = propagate(w, b, X, Y)
        dw, db = grads["dw"], grads["db"]

        w -= learning_rate * dw
        b -= learning_rate * db

        costs.append(cost)

        if i % 10 == 0:
            print(f"🔸 Iteration {i:4d}")
            print(f"   Cost       : {cost:.6f}")
            print(f"   dw norm    : {np.linalg.norm(dw):.6f}")
            print(f"   db         : {db:.6f}")
            print(f"   w[0]       : {w[0][0]:.6f}")
            print(f"   b          : {b:.6f}\n")
    print("✅ Backward Propagation Completed.\n")
    return w, b, costs

def predict(w, b, X):
    A = sigmoid(np.dot(w.T, X) + b)
    return (A > 0.5).astype(int)

def compute_accuracy(pred, Y):
    return 100 - np.mean(np.abs(pred - Y)) * 100

def model(X_train, Y_train, X_test, Y_test, num_iterations=2000, learning_rate=0.05):
    w, b = initialize_parameters(X_train.shape[0])
    w_init, b_init = w.copy(), b

    print("📌 Forward Propagation (Before Training):")
    acc_before = compute_accuracy(predict(w_init, b_init, X_train), Y_train)
    print(f"   Train Accuracy: {acc_before:.2f}%")
    print(f"   Test Accuracy : {compute_accuracy(predict(w_init, b_init, X_test), Y_test):.2f}%")

    w, b, costs = optimize(w, b, X_train, Y_train, num_iterations, learning_rate)

    print("📌 Forward Propagation (After Training):")
    acc_after = compute_accuracy(predict(w, b, X_train), Y_train)
    print(f"   Train Accuracy: {acc_after:.2f}%")
    print(f"   Test Accuracy : {compute_accuracy(predict(w, b, X_test), Y_test):.2f}%")

    # Plot cost and accuracy (points only)
    plt.scatter(range(num_iterations), costs, color='red', s=10, label='Cost (Backward)')
    plt.scatter(0, acc_before, color='blue', s=50, label='Initial Accuracy (Forward)')
    plt.scatter(num_iterations - 1, acc_after, color='green', s=50, label='Final Accuracy (Forward)')
    plt.title("Training Insights (Points Only)")
    plt.xlabel("Iterations")
    plt.ylabel("Metric Value")
    plt.legend()
    plt.grid()
    plt.show()

    return {
        "weights": w,
        "bias": b,
        "train_accuracy": acc_after,
        "test_accuracy": compute_accuracy(predict(w, b, X_test), Y_test),
        "costs": costs
    }

# --------------------------
# Decision Boundary Plot
# --------------------------

def plot_decision_boundary(w, b, X, Y):
    X = X.T
    Y = Y.flatten()

    x_min, x_max = X[:, 0].min() - 1, X[:, 0].max() + 1
    y_min, y_max = X[:, 1].min() - 1, X[:, 1].max() + 1
    xx, yy = np.meshgrid(np.linspace(x_min, x_max, 500),
                         np.linspace(y_min, y_max, 500))

    grid = np.c_[xx.ravel(), yy.ravel()].T
    Z = sigmoid(np.dot(w.T, grid) + b)
    Z = Z.reshape(xx.shape)

    plt.figure(figsize=(8, 6))
    plt.contourf(xx, yy, Z > 0.5, alpha=0.3, cmap=plt.cm.RdBu)

    plt.scatter(X[Y == 0][:, 0], X[Y == 0][:, 1], c='blue', label='Class 0')
    plt.scatter(X[Y == 1][:, 0], X[Y == 1][:, 1], c='red', label='Class 1')

    plt.contour(xx, yy, Z, levels=[0.5], linewidths=2, colors='black')

    plt.xlabel("Feature 1")
    plt.ylabel("Feature 2")
    plt.title("Decision Boundary")
    plt.legend()
    plt.grid(True)
    plt.show()

# --------------------------
# Load Real Data from make_classification
# --------------------------

X, Y = make_classification(
    n_samples=1000,
    n_features=2,
    n_informative=2,
    n_redundant=0,
    n_classes=2,
    random_state=1
)
X = X.T
Y = Y.reshape(1, -1)

# Split into train and test
X_train, X_test, Y_train, Y_test = train_test_split(X.T, Y.T, test_size=0.2, random_state=42)
X_train = X_train.T
X_test = X_test.T
Y_train = Y_train.T
Y_test = Y_test.T

# --------------------------
# Train & Visualize
# --------------------------

result = model(X_train, Y_train, X_test, Y_test, num_iterations=2000, learning_rate=0.05)
plot_decision_boundary(result["weights"], result["bias"], X_train, Y_train)
