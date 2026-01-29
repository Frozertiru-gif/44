import fs from "fs";
import path from "path";

const filePath = path.join(process.cwd(), "data", "leads.jsonl");

if (!fs.existsSync(filePath)) {
  console.log("Файл лидов не найден.");
  process.exit(0);
}

const content = fs.readFileSync(filePath, "utf8").trim();
if (!content) {
  console.log("Лидов пока нет.");
  process.exit(0);
}

const lines = content.split("\n").filter(Boolean);
const last = lines.slice(-20);

console.log("Последние лиды:");
for (const line of last) {
  try {
    const data = JSON.parse(line);
    console.log(`- ${data.ts} | ${data.phone} | ${data.name ?? "без имени"} | ${data.source}`);
  } catch (error) {
    console.log("- [ошибка чтения строки]");
  }
}
