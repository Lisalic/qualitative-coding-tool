import React, { useMemo, useCallback } from "react";
import CodeLegend from "./CodeLegend";
import {
  getUniqueCodes,
  getFilteredCoding,
  getPostDataById,
} from "../lib/codingUtils";

// Component for the table view of coding data
const CodingTableView = ({
  parsedCoding,
  postContents,
  selectedFilterCodes,
  setSelectedFilterCodes,
  getCodeColor,
  highlightContent,
}) => {
  const handleCodeToggle = useCallback(
    (code) => {
      setSelectedFilterCodes((prev) =>
        prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code],
      );
    },
    [setSelectedFilterCodes],
  );

  const uniqueCodes = useMemo(
    () => getUniqueCodes(parsedCoding),
    [parsedCoding],
  );

  const filteredCoding = useMemo(
    () => getFilteredCoding(parsedCoding, selectedFilterCodes),
    [parsedCoding, selectedFilterCodes],
  );

  return (
    <div>
      {selectedFilterCodes.length > 0 && (
        <div className="body-sm text-primary" style={{ marginBottom: "10px" }}>
          <strong>Filtering by codes:</strong> {selectedFilterCodes.join(", ")}{" "}
          <button
            onClick={() => setSelectedFilterCodes([])}
            className="btn btn-secondary btn-small"
          >
            Clear Filter
          </button>
        </div>
      )}
      <CodeLegend
        codes={uniqueCodes}
        selectedFilterCodes={selectedFilterCodes}
        onCodeToggle={handleCodeToggle}
        getCodeColor={getCodeColor}
      />

      <div className="table-wrapper">
        <table className="table">
          <thead>
            <tr>
              <th className="table__th">
                Post ID
              </th>
              <th className="table__th">
                Title
              </th>
              <th className="table__th">
                Content
              </th>
              <th className="table__th">
                Codes Applied
              </th>
            </tr>
          </thead>
          <tbody>
            {filteredCoding.map((item, index) => {
                const filteredCodeEvidence =
                  selectedFilterCodes.length > 0
                    ? item.codeEvidence.filter((ev) =>
                        selectedFilterCodes.includes(ev.code),
                      )
                    : item.codeEvidence;
                return (
                  <tr key={index} className="table__row--hover">
                    <td className="table__td" style={{ verticalAlign: "top", maxWidth: "250px" }}>
                      {item.postId}
                    </td>
                    <td className="table__td" style={{ verticalAlign: "top", maxWidth: "125px" }}>
                      <div style={{ whiteSpace: "pre-wrap", wordWrap: "break-word" }}>
                        {(() => {
                          const postData = getPostDataById(
                            postContents,
                            item.postId,
                          );
                          return postData ? postData.title : "Title not found";
                        })()}
                      </div>
                    </td>
                    <td className="table__td" style={{ verticalAlign: "top", maxWidth: "400px" }}>
                      <div style={{ whiteSpace: "pre-wrap", wordWrap: "break-word" }}>
                        {(() => {
                          const postData = getPostDataById(
                            postContents,
                            item.postId,
                          );
                          if (postData && postData.content) {
                            return (
                              <div style={{ whiteSpace: "pre-wrap", wordWrap: "break-word" }}>
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
                    <td className="table__td" style={{ verticalAlign: "top", maxWidth: "175px" }}>
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
                        <span className="text-muted">No codes applied</span>
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
