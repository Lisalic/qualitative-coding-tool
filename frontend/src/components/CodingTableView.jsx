import React from "react";
import CodeLegend from "./CodeLegend";
import { getUniqueCodes, getFilteredCoding } from "../lib/codingUtils";

// Component for the table view of coding data
const CodingTableView = ({
  parsedCoding,
  postContents,
  selectedFilterCodes,
  setSelectedFilterCodes,
  getCodeColor,
  highlightContent,
}) => {
  const handleCodeToggle = (code) => {
    setSelectedFilterCodes((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code],
    );
  };

  return (
    <div>
      {selectedFilterCodes.length > 0 && (
        <div style={{ marginBottom: "10px", color: "#fff" }}>
          <strong>Filtering by codes:</strong> {selectedFilterCodes.join(", ")}{" "}
          <button
            onClick={() => setSelectedFilterCodes([])}
            style={{
              backgroundColor: "#555",
              color: "#fff",
              border: "none",
              padding: "2px 6px",
              borderRadius: "3px",
              cursor: "pointer",
              fontSize: "0.8em",
            }}
          >
            Clear Filter
          </button>
        </div>
      )}
      <CodeLegend
        codes={getUniqueCodes(parsedCoding)}
        selectedFilterCodes={selectedFilterCodes}
        onCodeToggle={handleCodeToggle}
        getCodeColor={getCodeColor}
      />

      <div style={{ overflowX: "auto" }}>
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            backgroundColor: "#000",
            color: "#fff",
          }}
        >
          <thead>
            <tr style={{ backgroundColor: "#333" }}>
              <th
                style={{
                  padding: "12px",
                  border: "1px solid #555",
                  textAlign: "left",
                }}
              >
                Post ID
              </th>
              <th
                style={{
                  padding: "12px",
                  border: "1px solid #555",
                  textAlign: "left",
                }}
              >
                Title
              </th>
              <th
                style={{
                  padding: "12px",
                  border: "1px solid #555",
                  textAlign: "left",
                }}
              >
                Content
              </th>
              <th
                style={{
                  padding: "12px",
                  border: "1px solid #555",
                  textAlign: "left",
                }}
              >
                Codes Applied
              </th>
            </tr>
          </thead>
          <tbody>
            {getFilteredCoding(parsedCoding, selectedFilterCodes).map(
              (item, index) => {
                const filteredCodeEvidence =
                  selectedFilterCodes.length > 0
                    ? item.codeEvidence.filter((ev) =>
                        selectedFilterCodes.includes(ev.code),
                      )
                    : item.codeEvidence;
                return (
                  <tr key={index} style={{ borderBottom: "1px solid #333" }}>
                    <td
                      style={{
                        padding: "12px",
                        border: "1px solid #555",
                        verticalAlign: "top",
                        maxWidth: "250px",
                      }}
                    >
                      {item.postId}
                    </td>
                    <td
                      style={{
                        padding: "12px",
                        border: "1px solid #555",
                        verticalAlign: "top",
                        maxWidth: "125px",
                      }}
                    >
                      <div
                        style={{
                          whiteSpace: "pre-wrap",
                          wordWrap: "break-word",
                        }}
                      >
                        {(() => {
                          // Case-insensitive lookup for post content
                          const postIdLower = item.postId.toLowerCase();
                          const matchingKey = Object.keys(postContents).find(
                            (key) => key.toLowerCase() === postIdLower,
                          );
                          const postData = matchingKey
                            ? postContents[matchingKey]
                            : null;
                          console.log(
                            `Post ${item.postId}: content exists = ${!!postData} (matched key: ${matchingKey})`,
                          );
                          if (!postData) {
                            console.log(
                              `Available postContents keys:`,
                              Object.keys(postContents).slice(0, 10),
                            );
                          }
                          return postData ? postData.title : "Title not found";
                        })()}
                      </div>
                    </td>
                    <td
                      style={{
                        padding: "12px",
                        border: "1px solid #555",
                        verticalAlign: "top",
                        maxWidth: "400px",
                      }}
                    >
                      <div
                        style={{
                          whiteSpace: "pre-wrap",
                          wordWrap: "break-word",
                        }}
                      >
                        {(() => {
                          // Case-insensitive lookup for post content
                          const postIdLower = item.postId.toLowerCase();
                          const matchingKey = Object.keys(postContents).find(
                            (key) => key.toLowerCase() === postIdLower,
                          );
                          const postData = matchingKey
                            ? postContents[matchingKey]
                            : null;
                          if (postData && postData.content) {
                            return (
                              <div
                                style={{
                                  whiteSpace: "pre-wrap",
                                  wordWrap: "break-word",
                                }}
                              >
                                {highlightContent(
                                  postData.content,
                                  filteredCodeEvidence,
                                )}
                              </div>
                            );
                          }
                          return "Content not found";
                        })()}
                      </div>
                    </td>
                    <td
                      style={{
                        padding: "12px",
                        border: "1px solid #555",
                        verticalAlign: "top",
                        maxWidth: "175px",
                      }}
                    >
                      {filteredCodeEvidence.length > 0 ? (
                        <div>
                          {[
                            ...new Set(
                              filteredCodeEvidence.map(({ code }) => code),
                            ),
                          ].map((code) => (
                            <div
                              key={code}
                              style={{
                                display: "inline-block",
                                backgroundColor: getCodeColor(code),
                                color: "black",
                                padding: "4px 8px",
                                margin: "2px",
                                borderRadius: "4px",
                                fontSize: "0.9em",
                                fontWeight: "bold",
                              }}
                            >
                              {code}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <span style={{ color: "#888" }}>No codes applied</span>
                      )}
                    </td>
                  </tr>
                );
              },
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default CodingTableView;
