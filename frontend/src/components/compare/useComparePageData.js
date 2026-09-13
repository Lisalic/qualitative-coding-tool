import { useEffect, useState } from "react";
import { apiFetch } from "../../api";

export default function useComparePageData({
  fileType,
  initialA = "",
}) {
  const [items, setItems] = useState([]);
  const [a, setA] = useState(initialA || "");
  const [b, setB] = useState("");

  // Computed deterministic comparison states
  const [computedData, setComputedData] = useState(null);
  const [computedLoading, setComputedLoading] = useState(false);
  const [computedError, setComputedError] = useState("");

  useEffect(() => {
    setA(initialA || "");
  }, [initialA]);

  useEffect(() => {
    let mounted = true;
    apiFetch(`/api/my-files/?file_type=${fileType}`)
      .then((response) => (response.ok ? response.json() : null))
      .then((data) => {
        if (!mounted || !data) return;
        const list = (data.projects || []).map((project) => ({
          value: project.schema_name,
          label: project.display_name || project.schema_name,
        }));
        setItems(list);
        if (initialA) {
          const availableForB = list.filter((item) => item.value !== initialA);
          if (availableForB.length > 0) {
            setB((previousValue) => previousValue || availableForB[0].value);
          }
        }
      })
      .catch(() => {});

    return () => {
      mounted = false;
    };
  }, [fileType, initialA]);

  // Automatically compute deterministic comparison when both A and B are selected
  useEffect(() => {
    if (!a || !b) {
      setComputedData(null);
      setComputedError("");
      return;
    }

    let mounted = true;
    setComputedLoading(true);
    setComputedError("");

    const endpoint =
      fileType === "coding"
        ? `/api/comparison/codings?file_a=${encodeURIComponent(a)}&file_b=${encodeURIComponent(b)}`
        : `/api/comparison/codebooks?file_a=${encodeURIComponent(a)}&file_b=${encodeURIComponent(b)}`;

    apiFetch(endpoint)
      .then(async (res) => {
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || errData.error || "Failed to compute comparison");
        }
        return res.json();
      })
      .then((data) => {
        if (mounted) {
          setComputedData(data);
          setComputedLoading(false);
        }
      })
      .catch((err) => {
        if (mounted) {
          setComputedError(err.message);
          setComputedLoading(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [a, b, fileType]);

  const handleSwap = () => {
    const tempA = a;
    setA(b);
    setB(tempA);
  };

  return {
    items,
    a,
    b,
    setA,
    setB,
    handleSwap,
    computedData,
    computedLoading,
    computedError,
  };
}
