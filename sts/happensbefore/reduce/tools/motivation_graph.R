#!/bin/Rscript

# Usage (in this folder): Rscript test_loadbalancer_graph.R loadbalancer.csv 

# Parameters:
tsize <- 24         # Textsize
ylab_cex <- 1       # Scaling of y axis lables
lwd <- 4            # Linewidth
symb_cex <- 2       # Scaling of symbol size
llen <- 5           # Line length in legend


# Test Script to create a graph out of a csv
args <- commandArgs(TRUE)

if (length(args)!=1) {
  stop("Exactly one parameter needed (path to csv).n", call.=FALSE)
} else {
  csv_file <- args[1]
  eval_dir <- dirname(csv_file)
  out_file <- "../figures/motivation_graph.pdf"
}

data <- read.csv(file=csv_file, head=TRUE, sep=",")

d <- split(data, data$steps)


# Prepare Data
# prepare lines
s <- numeric(0)
race <- list(c(),c(),c())
clus <- list(c(),c(),c())


for (dat in d){
    s <- c(s, dat$steps[1])
    race[[1]] <- c(race[[1]], quantile(dat$races, c(0.50)))
    race[[2]] <- c(race[[2]], quantile(dat$races, c(0.05)))
    race[[3]] <- c(race[[3]], quantile(dat$races, c(0.95)))
    clus[[1]] <- c(clus[[1]], quantile(dat$clusters, c(0.50)))
    clus[[2]] <- c(clus[[2]], quantile(dat$clusters, c(0.05)))
    clus[[3]] <- c(clus[[3]], quantile(dat$clusters, c(0.95)))
}

# Prepare device
pdf(file=out_file, width=10, height=6)

# Prepare Plot
xrange <- range(data$steps)
 yrange1 <- c(0, 8000)#max(data$races))
yrange2 <- c(0, 10)


#colors <- rainbow(2)
colors <- c("black", "blue")
linetype <- c(1:length(race))
plotchar <- seq(15, 15+length(race), 1)


# New
par(mar = c(4, 9, 1, 5) + 0.3, ps=tsize, cex = 1, cex.main = 1)
plot(xrange, yrange1, type="n", xlab="Steps", ylab="", las=1)
axis(side=2, at = pretty(yrange1), col=colors[1], col.axis=colors[1], las=1)
mtext("Violations reported by SDNRacer", side=2, line=7, col=colors[1], las=0, cex=ylab_cex)
# End New

# Plot lines
for (i in 1:length(race)){
    lines(s, race[[i]], type="b", lwd=lwd, lty=linetype[i], col=colors[1], pch=plotchar[i], las=1, cex=symb_cex)
}

par(new = TRUE, ps=tsize, cex = 1, cex.main = 1)
plot(xrange, yrange2, type = "n", axes = FALSE, bty = "n", xlab = "", ylab = "")
axis(side=4, at = pretty(yrange2), col=colors[2], col.axis=colors[2], las=1)
mtext("Violations reported by BigBug", side=4, line=4, col=colors[2], cex=ylab_cex)

for (i in 1:length(clus)){
    lines(s, clus[[i]], type="b", lwd=lwd, lty=linetype[i], col=colors[2], pch=plotchar[i], cex=symb_cex)
}

# Title
#title("Races vs. Clusters", "Floodlight Loadbalancer StarTopology4")

# Single Legend
#legend("topleft",
#        legend=c("5th %-ile", "median", "95th %-ile", "5th %-ile", "median", "95th %-ile"),
#        text.col=c(colors[1], colors[1], colors[1], colors[2], colors[2], colors[2]),
#        pch=c(plotchar[2], plotchar[1], plotchar[3], plotchar[2], plotchar[1], plotchar[3]),
#        lty=c(linetype[2], linetype[1], linetype[3], linetype[2], linetype[1], linetype[3]),
#        col=c(colors[1], colors[1], colors[1], colors[2], colors[2], colors[2]),
#        pt.cex=symb_cex,
#        lwd=lwd,
#        seg.len=llen,
#        y.intersp=1.5)

legend("topleft",
        legend=c("5th %-ile", "median", "95th %-ile"),
        text.col=c(colors[1], colors[1], colors[1]),
        pch=c(plotchar[2], plotchar[1], plotchar[3]),
        lty=c(linetype[2], linetype[1], linetype[3]),
        col=c(colors[1], colors[1], colors[1]),
        pt.cex=symb_cex,
        lwd=lwd,
        seg.len=llen,
        y.intersp=1.5)

legend("bottomright",
        legend=c("5th %-ile", "median", "95th %-ile"),
        text.col=c(colors[2], colors[2], colors[2]),
        pch=c(plotchar[2], plotchar[1], plotchar[3]),
        lty=c(linetype[2], linetype[1], linetype[3]),
        col=c(colors[2], colors[2], colors[2]),
        pt.cex=symb_cex,
        lwd=lwd,
        seg.len=llen,
        y.intersp=1.5)

dev.off()

