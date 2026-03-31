const GITHUB_API = "https://api.github.com"

function validateToken(token) {
    return typeof token === "string" && token.trim().length > 10 && !/\s/.test(token)
}

function validateRepoName(name) {
    return typeof name === "string" && /^[a-zA-Z0-9_.-]+$/.test(name) && name.length > 0
}

function validateBranchName(branch) {
    return typeof branch === "string" && /^[a-zA-Z0-9._\-/]+$/.test(branch) && branch.length > 0
}

function validateFilePath(path) {
    return typeof path === "string" && /^[a-zA-Z0-9._\-/]+$/.test(path) && !path.startsWith("/")
}

async function ghFetch(path, token, options = {}) {
    return fetch(`${GITHUB_API}${path}`, {
        ...options,
        headers: {
            Authorization: `Bearer ${token}`,
            Accept: "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            ...(options.headers || {}),
        },
    })
}

export default async function handler(req, res) {
    if (req.method !== "POST") {
        return res.status(405).json({ error: "Method not allowed" })
    }

    const {
        action,
        token,
        owner,
        repo,
        branch,
        baseBranch,
        filePath,
        content,
        commitMessage,
        prTitle,
        prBody,
    } = req.body ?? {}

    // ── Common validation ──────────────────────────────────────────────────
    if (!validateToken(token)) {
        return res.status(400).json({ error: "Invalid or missing GitHub token" })
    }
    if (!validateRepoName(owner) || !validateRepoName(repo)) {
        return res.status(400).json({ error: "Invalid owner or repository name" })
    }

    try {
        // ── PUSH ──────────────────────────────────────────────────────────
        if (action === "push") {
            if (!branch || !filePath || content === undefined || !commitMessage) {
                return res.status(400).json({ error: "Missing required push parameters" })
            }
            if (!validateBranchName(branch)) {
                return res.status(400).json({ error: "Invalid branch name" })
            }
            if (!validateFilePath(filePath)) {
                return res.status(400).json({ error: "Invalid file path" })
            }
            if (typeof commitMessage !== "string" || commitMessage.trim().length === 0) {
                return res.status(400).json({ error: "Commit message cannot be empty" })
            }

            const base = baseBranch || "main"

            // 1. Get base branch SHA
            const baseRefRes = await ghFetch(
                `/repos/${owner}/${repo}/git/refs/heads/${base}`,
                token
            )
            if (!baseRefRes.ok) {
                const err = await baseRefRes.json()
                return res.status(400).json({ error: `Base branch "${base}" not found: ${err.message}` })
            }
            const { object: { sha: baseSha } } = await baseRefRes.json()

            // 2. Create target branch (ignore 422 = already exists)
            if (branch !== base) {
                const createBranchRes = await ghFetch(
                    `/repos/${owner}/${repo}/git/refs`,
                    token,
                    {
                        method: "POST",
                        body: JSON.stringify({ ref: `refs/heads/${branch}`, sha: baseSha }),
                    }
                )
                if (!createBranchRes.ok && createBranchRes.status !== 422) {
                    const err = await createBranchRes.json()
                    return res.status(400).json({ error: `Failed to create branch: ${err.message}` })
                }
            }

            // 3. Get existing file SHA for upsert
            let existingSha
            const existingRes = await ghFetch(
                `/repos/${owner}/${repo}/contents/${filePath}?ref=${encodeURIComponent(branch)}`,
                token
            )
            if (existingRes.ok) {
                const existingData = await existingRes.json()
                existingSha = existingData.sha
            }

            // 4. Create / update file
            const filePayload = {
                message: commitMessage.trim(),
                content: Buffer.from(content).toString("base64"),
                branch,
            }
            if (existingSha) filePayload.sha = existingSha

            const putRes = await ghFetch(
                `/repos/${owner}/${repo}/contents/${filePath}`,
                token,
                { method: "PUT", body: JSON.stringify(filePayload) }
            )
            if (!putRes.ok) {
                const err = await putRes.json()
                return res.status(400).json({ error: `Push failed: ${err.message}` })
            }

            const putData = await putRes.json()
            return res.status(200).json({
                success: true,
                commit: putData.commit.sha,
                branch,
                fileUrl: putData.content.html_url,
            })
        }

        // ── CREATE PR ─────────────────────────────────────────────────────
        if (action === "pr") {
            if (!prTitle || !branch || !baseBranch) {
                return res.status(400).json({ error: "Missing required PR parameters" })
            }
            if (typeof prTitle !== "string" || prTitle.trim().length === 0) {
                return res.status(400).json({ error: "PR title cannot be empty" })
            }
            if (!validateBranchName(branch) || !validateBranchName(baseBranch)) {
                return res.status(400).json({ error: "Invalid branch name" })
            }

            const prRes = await ghFetch(`/repos/${owner}/${repo}/pulls`, token, {
                method: "POST",
                body: JSON.stringify({
                    title: prTitle.trim(),
                    head: branch,
                    base: baseBranch,
                    body: typeof prBody === "string" ? prBody : "",
                }),
            })
            if (!prRes.ok) {
                const err = await prRes.json()
                return res.status(400).json({ error: `PR creation failed: ${err.message}` })
            }

            const prData = await prRes.json()
            return res.status(200).json({
                success: true,
                prUrl: prData.html_url,
                prNumber: prData.number,
            })
        }

        return res.status(400).json({ error: "Unknown action" })
    } catch (err) {
        console.error("GitHub handler error:", err)
        return res.status(500).json({ error: "Internal server error" })
    }
}
